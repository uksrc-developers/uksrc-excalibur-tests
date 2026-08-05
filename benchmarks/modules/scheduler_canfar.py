import itertools, os, time

from reframe.core.backends import register_scheduler
from reframe.core.exceptions import JobError, JobSchedulerError
from reframe.core.schedulers import JobScheduler, Job

class _CanfarJob(Job):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._session_name = None
        self._cancelled = False

    @property
    def session_name(self):
        return self._session_name

    @property
    def cancelled(self):
        return self._cancelled

@register_scheduler('canfar')
class CanfarJobScheduler(JobScheduler):
    '''Canfar job scheduler for ReFrame.

    Submits tests as Canfar job using Canfar python API. Intended for use
    with tests that inherit from ContainerTest.

    Any scheduler that submits container jobs should set:
        container_scheduler = True

    This convention allows ContainerTest (and its subclasses) to detect
    container-aware schedulers without hardcoding scheduler names.

    Usage in site_configuration partitions:
        {
            'name': '<partition name>',
            'scheduler': 'canfar',
            'launcher': 'local',
            'access': [
                '--image=<image>:latest',
                '--namespace=benchmarks',
            ],
        }
    '''
    try:
        from canfar.sessions import Session
        connection_session = Session()
    except ImportError:
        connection_session = None
    container_scheduler = True

    def make_job(self, *args, **kwargs):
        return _CanfarJob(*args, **kwargs)

    def emit_preamble(self, job):
        return []

    def allnodes(self):
        raise NotImplementedError('canfar scheduler does not support node listing')

    def filternodes(self, job, nodes):
        raise NotImplementedError('canfar scheduler does not support node filtering')

    def submit(self, job):
        open(os.path.join(job.outputdir.replace('/output/', '/stage/'), job.stdout), 'w').close()
        open(os.path.join(job.outputdir.replace('/output/', '/stage/'), job.stderr), 'w').close()
        if self.connection_session is None:
            raise JobSchedulerError('canfar package is required for the canfar scheduler')
        job._session_name = job.name.lower()[:job.name.find(' ')]
        try:
            command = "{precmd}echo Workflow start: $(date \"+%Y-%m-%d %H:%M:%S\");{cmd};echo Workflow end: $(date \"+%Y-%m-%d %H:%M:%S\")".format(precmd=job.container_precmd.replace('\n', ';'), cmd=job.container_cmd)
            print('submitting job with cmd: \n{}'.format(command.replace("\t", " ")))
            job._jobid =  self.connection_session.create(
                name="headless-test",
                image=job.container_image,
                kind="headless",
                cmd="bash",
                env=job.env_variables,
                # in order to allow commands to remain as one argument for "bash -c <commands>" we replace the spaces with \t
                args="-c " + command
            )[0]
            print(f"Session ID = {job._jobid}")
        except:
            print("Error in CanfarJobScheduler.submit")
            raise JobError
        job._submit_time = time.time()
        job._state = self.connection_session.info(job._jobid)[0]["status"]
        self.log(f'submitted canfar job: {job._jobid}')
        open(os.path.join(job.outputdir, job.stdout), 'w').close()
        open(os.path.join(job.outputdir, job.stderr), 'w').close()

    def cancel(self, job):
        #self.connection_session.destroy(job._jobid)
        job._cancelled = True

    def wait(self, job):
        intervals = itertools.cycle([5, 10, 20])
        while not self.finished(job):
            self.poll(job)
            time.sleep(next(intervals))

    def finished(self, job):
        if job._state != 'Completed' and job._state != 'Failed':
            return False
        return True

    def poll(self, *jobs):
        for job in jobs:
            if job is not None and job._jobid is not None:
                self._poll_job(job)


    def _poll_job(self, job):
        try:
            status = self.connection_session.info(job._jobid)[0]["status"]
        except:
            if "The read operation timed out" in self.connection_session.info(job._jobid):
                return
            print("Unable to get status.")
            print(f"Job ID = {job._jobid}")
            print(f"connection_session.info = {self.connection_session.info(job._jobid)}")
            status = "Failed"

        job._state = status
        if status == 'Completed':
            job._exitcode = 0
            self._retrieve_logs(job)
            return
        elif status == 'Failed':
            job._exitcode = 1
            self._retrieve_logs(job)
            return
        if (job._state == 'Pending' and job.max_pending_time
                and time.time() - job.submit_time >= job.max_pending_time):
            self.cancel(job)
            job._exception = JobError('maximum pending time exceeded', job.jobid)
            return

    def _retrieve_logs(self, job):
        if job._state != "Completed" and job._state != "Failed":
            return

        logs = self.connection_session.logs(job._jobid)[job._jobid]

        with open(os.path.join(job.outputdir, "container_job.out"), 'w') as f:
            f.write(logs)