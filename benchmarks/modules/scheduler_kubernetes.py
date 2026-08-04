import itertools
import json
import os
import time
import secrets

import yaml
from reframe.core.backends import register_scheduler
from reframe.core.exceptions import JobError, JobSchedulerError
from reframe.core.schedulers import JobScheduler, Job
from reframe.utility import osext

class _KubernetesJob(Job):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._job_name = None
        self._pod_name = None
        self._namespace = None
        self._manifest_path = None
        self._cancelled = False

    @property
    def job_name(self):
        return self._job_name

    @property
    def pod_name(self):
        return self._pod_name

    @property
    def namespace(self):
        return self._namespace

    @property
    def manifest_path(self):
        return self._manifest_path

    @property
    def cancelled(self):
        return self._cancelled

@register_scheduler('k8s')
class KubernetesJobScheduler(JobScheduler):
    '''Kubernetes job scheduler for ReFrame.

    Submits tests as Kubernetes batch jobs using kubectl. Intended for use
    with tests that inherit from ContainerTest.

    Any scheduler that submits container jobs should set:
        container_scheduler = True

    This convention allows ContainerTest (and its subclasses) to detect
    container-aware schedulers without hardcoding scheduler names.

    Usage in site_configuration partitions:
        {
            'name': '<partition name>',
            'scheduler': 'k8s',
            'launcher': 'local',
            'access': [
                '--image=<image>:latest',
                '--namespace=benchmarks',
            ],
        }
    '''

    container_scheduler = True

    _MAX_NAME_LEN = 63
    _SUFFIX_LEN = 6  # hex chars
    _BASE_NAME_LEN = _MAX_NAME_LEN - _SUFFIX_LEN - 1

    @staticmethod
    def _namespace_from_options(job):
        for opt in (*job.sched_access, *job.options, *job.cli_options):
            if opt.startswith('--namespace='):
                return opt.split('=', 1)[1]
        return 'default'

    @staticmethod
    def _pull_policy_from_options(job):
        for opt in (*job.sched_access, *job.options, *job.cli_options):
            if opt.startswith('--pull-policy='):
                return opt.split('=', 1)[1]
        return None

    def _build_manifest(self, job):
        job_name = job._job_name
        namespace = job._namespace

        command = f"{job.container_precmd}\necho Workflow start: $(date \"+%Y-%m-%d %H:%M:%S\")\n{job.container_cmd}\necho Workflow end: $(date \"+%Y-%m-%d %H:%M:%S\")"
        container = {
            'name': job_name,
            'image': job.container_image.replace("docker://", ""),
            'command':  ["/bin/bash", "-c", command],
        }
        if job.env_variables:
            container['env'] = [{"name": k, "value": v} for k, v in job.env_variables.items()]

        pull_policy = self._pull_policy_from_options(job)
        if pull_policy:
            container['imagePullPolicy'] = pull_policy

        if job.num_cpus_per_task:
            container['resources'] = {
                'requests': {'cpu': str(job.num_cpus_per_task)},
                'limits': {'cpu': str(job.num_cpus_per_task)},
            }

        job_spec = {
            'backoffLimit': 0,
            'template': {
                'spec': {
                    'restartPolicy': 'Never',
                    'containers': [container],
                }
            },
        }

        if job.time_limit is not None:
            job_spec['activeDeadlineSeconds'] = int(job.time_limit)

        return {
            'apiVersion': 'batch/v1',
            'kind': 'Job',
            'metadata': {'name': job_name, 'namespace': namespace},
            'spec': job_spec,
        }

    def make_job(self, *args, **kwargs):
        return _KubernetesJob(*args, **kwargs)

    def emit_preamble(self, job):
        return []

    def allnodes(self):
        raise NotImplementedError('k8s scheduler does not support node listing')

    def filternodes(self, job, nodes):
        raise NotImplementedError('k8s scheduler does not support node filtering')

    def submit(self, job):
        open(os.path.join(job.outputdir.replace('/output/', '/stage/'), job.stdout), 'w').close()
        open(os.path.join(job.outputdir.replace('/output/', '/stage/'), job.stderr), 'w').close()
        if yaml is None:
            raise JobSchedulerError('PyYAML is required for the k8s scheduler')

        job._namespace = self._namespace_from_options(job)
        base_name = job.name.lower()[:self._BASE_NAME_LEN].replace("_", "-")
        job._job_name = self._unique_pod_name(base_name, job._namespace)

        manifest = self._build_manifest(job)
        manifest_path = os.path.join(job.workdir, f'{job.name}_manifest.yaml')

        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f)

        job._manifest_path = manifest_path

        osext.run_command(f'kubectl apply -f {manifest_path}', check=True)

        pod  = osext.run_command(
            f'kubectl get pods -n {job._namespace}'
        ).stdout
        job._pod_name = pod[pod.find(job._job_name):].split()[0]

        job._jobid = job._job_name
        job._submit_time = time.time()
        job._state = 'QUEUED'
        self.log(f'submitted k8s job: {job._jobid}')

    def cancel(self, job):
        osext.run_command(
            f'kubectl delete job {job._job_name} '
            f'-n {job._namespace} --ignore-not-found',
            check=True,
        )
        job._cancelled = True

    def wait(self, job):
        intervals = itertools.cycle([1, 2, 3])
        while not self.finished(job):
            self.poll(job)
            time.sleep(next(intervals))

    def finished(self, job):
        if job._state != 'COMPLETED':
            return False
        stdout = os.path.join(job.outputdir, job.stdout)
        stderr = os.path.join(job.outputdir, job.stderr)
        return os.path.exists(stdout) and os.path.exists(stderr)

    def poll(self, *jobs):
        for job in jobs:
            if job is not None and job._jobid is not None:
                self._poll_job(job)

    def _poll_job(self, job):
        completed = osext.run_command(
            f'kubectl get job {job._job_name} -n {job._namespace} -o json'
        )

        if completed.returncode != 0:
            if 'not found' in completed.stderr.lower():
                job._state = 'COMPLETED'
                job._exitcode = 1
                self._retrieve_logs(job)
            else:
                self.log(f'kubectl get job returned error for {job._job_name}: {completed.stderr.strip()}')
            return

        try:
            status = json.loads(completed.stdout).get('status', {})
        except json.JSONDecodeError:
            return

        for cond in status.get('conditions', []):
            ctype = cond.get('type')
            if cond.get('status') != 'True':
                continue
            if ctype == 'Complete':
                job._state = 'COMPLETED'
                job._exitcode = 0
                self._retrieve_logs(job)
                return
            if ctype == 'Failed':
                job._state = 'COMPLETED'
                job._exitcode = 1
                self._retrieve_logs(job)
                return

        job._state = 'RUNNING' if status.get('active', 0) > 0 else 'QUEUED'

        if (job._state == 'QUEUED' and job.max_pending_time
                and time.time() - job.submit_time >= job.max_pending_time):
            self.cancel(job)
            job._exception = JobError('maximum pending time exceeded', job.jobid)

    @staticmethod
    def _job_status(name, namespace):
        '''Return the current status of a k8s job by name.

        Returns one of 'complete', 'failed', 'active' (covers Running/
        Pending), or None if the job does not exist.
        '''
        completed = osext.run_command(
            f'kubectl get job {name} -n {namespace} -o json'
        )
        if completed.returncode != 0:
            return None

        try:
            status = json.loads(completed.stdout).get('status', {})
        except json.JSONDecodeError:
            return None

        for cond in status.get('conditions', []):
            if cond.get('status') != 'True':
                continue
            if cond.get('type') == 'Complete':
                return 'complete'
            if cond.get('type') == 'Failed':
                return 'failed'

        return 'active'

    def _unique_pod_name(self, base_name, namespace):
        '''Resolve a usable, collision-free pod name for a new job.

        If a job with the candidate name exists but is in a terminal
        state (Complete/Failed), it is deleted and the name is reused.
        If it exists and is still active (Running/Pending), a new name
        with a random suffix is generated instead.
        '''
        candidate = base_name
        while True:
            status = self._job_status(candidate, namespace)

            if status is None:
                return candidate

            if status in ('complete', 'failed'):
                osext.run_command(
                    f'kubectl delete job {candidate} -n {namespace} '
                    f'--ignore-not-found',
                    check=True,
                )
                return candidate

            # status == 'active': name is taken by a running/pending job
            suffix = secrets.token_hex(self._SUFFIX_LEN // 2)
            candidate = f'{base_name[:self._BASE_NAME_LEN]}-{suffix}'

    def _retrieve_logs(self, job):
        completed = osext.run_command(
            f'kubectl get pods -n {job._namespace} {job._pod_name} '
            f'-o jsonpath=\'{{.metadata.name}}\''
        )

        pod_name = completed.stdout.strip("'").strip()

        if not pod_name or completed.returncode != 0:
            open(os.path.join(job.workdir, job.stdout), 'a').close()
            open(os.path.join(job.workdir, job.stderr), 'a').close()
            return

        logs = osext.run_command(
            f'kubectl logs {job._pod_name}'
        )

        with open(os.path.join(job.outputdir, "kubernetes_job.out"), 'w') as f:
            f.write(logs.stdout)