#!/usr/bin/env python
"""
pspec_pipe.py
-----------------------------------------
Copyright (c) 2020 The HERA Collaboration

This script is used as the IDR2 power
spectrum pipeline.

See pspec_pipe.yaml for relevant parameter selections.
"""
import multiprocess
import numpy as np
import hera_cal as hc
import hera_pspec as hp
from pyuvdata import UVData, UVBeam, UVCal
import pyuvdata.utils as uvutils
import os, sys, glob, yaml
from datetime import datetime
import uvtools as uvt
import json
import itertools
import aipy
import shutil
from collections import OrderedDict as odict
from scipy.interpolate import interp1d
from astropy import constants
import subprocess


#-------------------------------------------------------------------------------
# Parse YAML Configuration File
#-------------------------------------------------------------------------------
# get config and load dictionary
config = sys.argv[1]
cf = hp.utils.load_config(config)

# consolidate IO, data and analysis parameter dictionaries
params = odict(  list(cf['io'].items()) 
               + list(cf['data'].items()) 
               + list(cf['analysis'].items()) )
assert len(params) == len(cf['io']) + len(cf['data']) + len(cf['analysis']), ""\
       "Repeated parameters found within the scope of io, data and analysis dicts"
algs = cf['algorithm']
params['data_template'] = os.path.join(params['data_root'], params['data_template'])
if params['std_template'] is not None:
    params['std_template'] = os.path.join(params['data_root'], params['std_template'])

# Extract certain parameters used across the script
verbose = params['verbose']
overwrite = params['overwrite']
data_template = params['data_template']
std_template = params['std_template']
exclude_patterns = params['exclude_patterns']
cal_ext = params['cal_ext']
filetype = params['filetype']
group_pair = params['group_pair']
pol_pairs = params['pol_pairs']

# parse data_template and get dset dictionaries
dset1 = sorted(set(hp.utils.flatten([glob.glob(data_template.format(group=group_pair[0], pol=pp[0])) for pp in pol_pairs])))
dset2 = sorted(set(hp.utils.flatten([glob.glob(data_template.format(group=group_pair[1], pol=pp[1])) for pp in pol_pairs])))
if std_template is not None:
    std1 = sorted(set(hp.utils.flatten([glob.glob(std_template.format(group=group_pair[0], pol=pp[0])) for pp in pol_pairs])))
    std2 = sorted(set(hp.utils.flatten([glob.glob(std_template.format(group=group_pair[1], pol=pp[1])) for pp in pol_pairs])))
else:
    std1, std2 = None, None

# exclude patterns
if exclude_patterns not in [[], '', None, 'None']:
    if isinstance(exclude_patterns, (str, np.str)):
        exclude_patterns = [exclude_patterns]
    dset1 = [df for df in dset1 if not np.any([pattern in df for pattern in exclude_patterns])]
    dset2 = [df for df in dset2 if not np.any([pattern in df for pattern in exclude_patterns])]
    if std_template is not None:
        std1 = [df for df in std1 if not np.any([pattern in df for pattern in exclude_patterns])]
        std2 = [df for df in std2 if not np.any([pattern in df for pattern in exclude_patterns])]

d1_Nfiles, d2_Nfiles = len(dset1), len(dset2)
print("dset1 = {} files and dset2 = {} files".format(d1_Nfiles, d2_Nfiles))

# sort datafiles in time, taking into account the branch cut in LST
_, _, filelsts1, filetimes1 = hc.io.get_file_times(dset1, filetype='uvh5')
_, _, filelsts2, filetimes2 = hc.io.get_file_times(dset2, filetype='uvh5')
if params.get('lst_sort', False):
    branch_sorter = lambda x: (x[1] - params.get('lst_branch_cut', 0) + 2 * np.pi) % (2 * np.pi)
    timeorder1 = np.array(sorted([(i, fl[0]) for i, fl in enumerate(filelsts1)], key=branch_sorter), dtype=int)[:, 0]
    timeorder2 = np.array(sorted([(i, fl[0]) for i, fl in enumerate(filelsts2)], key=branch_sorter), dtype=int)[:, 0]
else:
    timeorder1 = np.argsort([ft[0] for ft in filetimes1])
    timeorder2 = np.argsort([ft[0] for ft in filetimes2])
dset1 = [dset1[ti] for ti in timeorder1]
dset2 = [dset2[ti] for ti in timeorder2]
if std_template is not None:
    std1 = [dset1[ti] for ti in timeorder1]
    std2 = [dset2[ti] for ti in timeorder2]

# get calibration files
cals1, cals2 = None, None
if cal_ext not in ['', None, 'None']:
    # try to use cal_ext as a full path to a single calibration
    cfiles = glob.glob(cal_ext)
    if len(cfiles) == 1:
        cals1 = cfiles[0]
        cals2 = cfiles[0]
    # otherwise interpret as file extension to dset
    else:
        cals1 = ["{}.{}".format(os.path.splitext(df)[0], cal_ext) for df in dset1]
        cals2 = ["{}.{}".format(os.path.splitext(df)[0], cal_ext) for df in dset2]

#-------------------------------------------------------------------------------
# Open log file and start running
#-------------------------------------------------------------------------------
# open logfile
logfile = os.path.join(params['out_dir'], params['logfile'])
if os.path.exists(logfile) and params['overwrite'] == False:
    raise IOError("logfile {} exists and overwrite == False, quitting pipeline...".format(logfile))
lf = open(logfile, "w")
if params['joinlog']:
    ef = lf
else:
    ef = open(os.path.join(params['out_dir'], params['errfile']), "w")
time = datetime.utcnow()
hp.utils.log("Starting pspec pipeline on {}\n{}\n".format(time, '-'*60), f=lf, verbose=params['verbose'])
hp.utils.log(json.dumps(cf, indent=1) + '\n', f=lf, verbose=params['verbose'])

# define history prepend function
def prepend_history(action, param_dict):
    """ create a history string to prepend to data files """
    dict_str = '\n'.join(["{} : {}".format(*_d) for _d in param_dict.items()])
    time = datetime.utcnow()
    hist = "\nRan pspec_pipe.py {} step at\nUTC {} with \nhera_pspec [{}], "\
           "and pyuvdata [{}]\nwith {} algorithm "\
           "attrs:\n{}\n{}\n".format(action, time, hp.version.git_hash[:10],
                                     pyuvdata.version.git_hash[:10], action, '-'*50, dict_str)
    return hist

# Create multiprocesses
if params['multiproc']:
    pool = multiprocess.Pool(params['nproc'])
    M = pool.map
else:
    M = map

# change to working dir
if os.path.isdir(params['work_dir']):
    subprocess.run(['rm', '-rf', params['work_dir']])
os.makedirs(params['work_dir'])
os.chdir(params['work_dir'])

# out_dir should be cleared before each run: issue a warning if not the case
oldfiles = glob.glob(params['out_dir']+"/*")
if len(oldfiles) > 0:
    hp.utils.log("\n{}\nWARNING: out_dir should be cleaned before each new run to " \
                 "ensure proper functionality.\nIt seems like some files currently " \
                 "exist in {}\n{}\n".format('-'*50, params['out_dir'], '-'*50), f=lf, verbose=params['verbose'])

#-------------------------------------------------------------------------------
# Run Visibility Data Difference
#-------------------------------------------------------------------------------
if params['run_diff']:
    # start block
    time = datetime.utcnow()
    hp.utils.log("\n{}\nstarting {} visibility data difference: {}\n".format("-"*60, algs['diff']['diff_type'], time), f=lf, verbose=params['verbose'])

    raise NotImplementedError


#-------------------------------------------------------------------------------
# Run QE Pipeline
#-------------------------------------------------------------------------------
if params['run_pspec']:
    # start block
    time = datetime.utcnow()
    hp.utils.log("\n{}\nstarting pspec QE: {}\n".format("-"*60, time), f=lf, verbose=params['verbose'])

    # configure dataset blpairs from first file in dset1
    uvd = UVData()
    uvd.read(dset1[0], read_data=False, file_type=params['filetype'])

    Nblps_per_job = algs['pspec']['Nblps_per_job']
    if Nblps_per_job in ['', None]:
        # if not specified, assume all blps in one job
        Nblps_per_job = 1000000

    # get baseline pairs grouped by redundant type
    (bls1, bls2, blps, x1, x2, reds, lens,
     angs) = hp.utils.calc_blpair_reds(uvd, uvd, filter_blpairs=params['filetype']=='uvh5',
                                       exclude_auto_bls=cf['algorithm']['pspec']['exclude_auto_bls'],
                                       exclude_cross_bls=cf['algorithm']['pspec']['exclude_cross_bls'],
                                       exclude_permutations=cf['algorithm']['pspec']['exclude_permutations'],
                                       bl_len_range=params['bl_len_range'], bl_deg_range=params['bl_deg_range'],
                                       xants=params['xants'], Nblps_per_group=Nblps_per_job, extra_info=True)
    Nblps = len(hp.utils.flatten(blps))

    # create dictionary of individual jobs to launch
    # parallelized over blpairs.
    # each task must compute all spws and polpairs due to
    # current uvp concatenation limitations
    jobs = odict()
    labels = odict()
    if cf['algorithm']['pspec']['output_by_red']:
        # already sorted by redundant group from calc_blpair_reds
        Njobs = len(blps)
        for i, _blps in enumerate(blps):
            jobs[i] = _blps
            labels[i] = "{:03.0f}m-{:03.0f}d".format(lens[reds[i][0]], angs[reds[i][0]])
    else:
        # unsort by redundant group and re-sort by Nblps_per_job
        bls1 = hp.utils.flatten(bls1)
        bls2 = hp.utils.flatten(bls2)
        blps = hp.utils.flatten(blps)
        job_counter = 0
        if Nblps == Nblps_per_job:
            Njobs = 1
        else:
            Njobs = Nblps // Nblps_per_job + 1
        job_blps = [blps[i * Nblps_per_job:(i + 1) * Nblps_per_job] for i in range(Njobs)]
        for _blps in job_blps:
            if len(_blps) > 0:
                jobs[job_counter] = _blps
                labels[job_counter] = None
                job_counter += 1

    hp.utils.log("\nTotal no. of jobs: {}.\n".format(len(jobs)), f=lf, verbose=params['verbose'])

    # make outfname
    outfname = os.path.join(params['out_dir'], algs['pspec']['outfname'])

    # create pspec worker function
    def pspec(i, jobs=jobs, labels=labels, params=params, pol_pairs=pol_pairs, alg=algs['pspec'],
              outfname=outfname, dset1=dset1, dset2=dset2, cals1=cals1, cals2=cals2):
        job_start = datetime.utcnow()
        hp.utils.log("\nPSPEC starting job {} / {}\n".format(i + 1, len(jobs)), f=lf, 
                     verbose=params['verbose'])
        try:
            # get blpairs
            blps = jobs[i]

            # configure dset pairs
            if dset1 == dset2:
                # if taking auto-dset spectra, don't load them twice
                # just set dset_pairs to (0, 0)
                dsets = [dset1]
                dset_pairs = [(0, 0)]
                if std_template is not None:
                    dsets_std = [std1]
                else:
                    dsets_std = None
                if cal_ext not in ['', None]:
                    cals = [cals1]
                else:
                    cals = None

            else:
                # cross dset spectra
                dsets = [dset1, dset2]
                dset_pairs = [(0, 1)]
                if std_template is not None:
                    dsets_std = [std1, std2]
                else:
                    dsets_std = None
                if cal_ext not in ['', None]:
                    cals = [cals1, cals2]
                else:
                    cals = None

            if labels[i] is None:
                dset_labels = ["{}+{}files".format(os.path.basename(_dsets[0]), len(_dsets) - 1) for _dsets in dsets]
            else:
                dset_labels = [labels[i] for _dsets in dsets]

            print("dsets:\n{}".format('\n\n'.join(['\n'.join([os.path.basename(f) for f in _dsets]) for _dsets in dsets])))

            # pspec_run
            hp.pspecdata.pspec_run(dsets, outfname, 
                                   dsets_std=dsets_std,
                                   cals=cals,
                                   cal_flag=params['cal_flag'],
                                   dset_labels=dset_labels,
                                   groupname=alg['groupname'],
                                   dset_pairs=dset_pairs,
                                   spw_ranges=alg['spw_ranges'],
                                   n_dlys=alg['n_dlys'],
                                   pol_pairs=pol_pairs, 
                                   blpairs=blps, 
                                   input_data_weight=alg['input_data_weight'],
                                   norm=alg['norm'], 
                                   taper=alg['taper'], 
                                   beam=alg['beam'], 
                                   cosmo=alg['cosmo'],
                                   cov_model=alg['cov_model'],
                                   store_cov_diag=alg['cov_model'] not in ['', 'None', None],
                                   interleave_times=alg['interleave_times'],
                                   rephase_to_dset=alg['rephase_to_dset'], 
                                   trim_dset_lsts=alg['trim_dset_lsts'],
                                   broadcast_dset_flags=alg['broadcast_dset_flags'], 
                                   time_thresh=alg['time_thresh'],
                                   Jy2mK=alg['Jy2mK'], 
                                   overwrite=params['overwrite'], 
                                   psname_ext="_{:04d}".format(i),
                                   file_type=params['filetype'],
                                   store_window=alg['store_window'],
                                   verbose=params['verbose'],
                                   tsleep=alg['tsleep'],
                                   maxiter=alg['maxiter'])
        except:
            hp.utils.log("\nPSPEC job {} errored with:".format(i), f=ef, tb=sys.exc_info(), verbose=params['verbose'])
            return 1
        
        hp.utils.log("\nPSPEC finished job {} / {} in {}\n".format(i + 1, len(jobs), datetime.utcnow() - job_start), 
                     f=lf, verbose=params['verbose'])
        return 0

    # launch pspec jobs
    failures = hp.utils.job_monitor(pspec, range(len(jobs)), "PSPEC", lf=lf, M=M,
                                    maxiter=params['maxiter'], verbose=params['verbose'])

    # print failures if they exist
    if len(failures) > 0:
        hp.utils.log("\nSome PSPEC jobs failed after {} tries:\n{}".format(params['maxiter'], '\n'.join(["job {}: {}".format(i, str(list(jobs.keys())[i])) for i in failures])), f=lf, verbose=params['verbose'])

    # Merge power spectrum files from separate jobs
    hp.utils.log("\nStarting power spectrum file merge: {}\n".format(time), f=lf, verbose=params['verbose'])

    # Get all groups
    psc = hp.PSpecContainer(outfname, 'rw')
    groups = psc.groups()
    del psc

    # Define merge function
    def merge(i, groups=groups, filename=outfname, ef=ef, params=params):
        try:
            psc = hp.PSpecContainer(filename, mode='rw')
            grp = groups[i]
            hp.container.combine_psc_spectra(psc, groups=[grp], merge_history=False, overwrite=params['overwrite'], verbose=False)
        except Exception as exc:
            print(exc)
            hp.utils.log("\nPSPEC MERGE job {} errored with:".format(i), f=ef, tb=sys.exc_info(), verbose=params['verbose'])
            return 1
        return 0

    # launch pspec merge jobs
    failures = hp.utils.job_monitor(merge, range(len(groups)), "PSPEC MERGE", lf=lf, maxiter=params['maxiter'], verbose=params['verbose'])

    # print failures if they exist
    if len(failures) > 0:
        hp.utils.log("\nSome PSPEC MERGE jobs failed after {} tries:\n{}".format(params['maxiter'], '\n'.join(["group {}: {}".format(i, str(groups[i])) for i in failures])), f=lf, verbose=params['verbose'])

    # print to log
    time = datetime.utcnow()
    hp.utils.log("\nFinished PSPEC pipeline: {}\n{}".format(time, "-"*60), f=lf, verbose=params['verbose'])

#-------------------------------------------------------------------------------
# Run thermal noise calculation
#-------------------------------------------------------------------------------
if params['run_noise_err']:
    # start block
    time = datetime.utcnow()
    hp.utils.log("\n{}\nStarting noise error pipeline: {}\n".format("-"*60, time), f=lf, verbose=params['verbose'])

    # ensure outfname is same as pspec if running both
    psc_fname = os.path.join(params['out_dir'], algs['noise_err']['psc_name'])
    if params['run_pspec'] and (outfname != psc_fname):
        raise ValueError("noise error psc_name {} doesn't equal pspec outfname {}".format(psc_fname, outfname))

    # define noise_err function
    def noise_err(psc_name, alg=algs['noise_err'], params=params):
        try:
            # define auto pols
            AUTOVISPOLS = ['XX', 'YY', 'EE', 'NN']
            STOKPOLS = ['PI', 'PQ', 'PU', 'PV']
            AUTOPOLS = AUTOVISPOLS + STOKPOLS

            # get container
            psc = hp.PSpecContainer(psc_name, mode='rw', keep_open=False, swmr=False)

            # get spectra
            groups = psc.groups()
            group = alg['group_name']
            assert group in groups, "{} not in groups".format(group)
            spectra = psc.spectra(group)
            if alg['spectra_names'] not in ['', None, 'None', 'none']:
                if not isinstance(alg['spectra_names'], (tuple, list)):
                    alg['spectra_names'] = [alg['spectra_names']]
                spectra = [sp for sp in alg['spectra_names'] if sp in spectra]

            # sort data in time to before loading autocorrelations
            dfiles = sorted(glob.glob(os.path.join(params['data_root'], alg['auto_file'])))
            assert len(dfiles) > 0
            _, _, filelsts, filetimes = hc.io.get_file_times(dfiles, filetype='uvh5')
            if params.get('lst_sort', False):
                branch_sorter = lambda x: (x[1] - params.get('lst_branch_cut', 0) + 2 * np.pi) % (2 * np.pi)
                timeorder = np.array(sorted([(i, fl[0]) for i, fl in enumerate(filelsts)], key=branch_sorter), dtype=int)[:, 0]
            else:
                timeorder = np.argsort([ft[0] for ft in filetimes])
            dfiles = [dfiles[ti] for ti in timeorder]

            # load autocorrelation file and its metadata
            uvd = UVData()
            uvd.read(dfiles[0], read_data=False)
            bls = [bl for bl in uvd.get_antpairs() if bl[0] == bl[1]]
            pols = [pol for pol in uvd.get_pols() if pol.upper() in AUTOPOLS]
            # if pseudo Stokes pol in pols, substitute for pI
            pols = sorted(set([pol if pol.upper() in AUTOVISPOLS else 'pI' for pol in pols]))
            uvd.read(dfiles, bls=bls, polarizations=pols)

            # apply calibration if passed
            if alg['cal_ext'] not in ['', None, 'None', 'none']:
                # try to use cal_ext as a full path to a single or multiple calibration(s)
                cfiles = sorted(glob.glob(cal_ext))
                if len(cfiles) == 0:
                    # didn't work, assume its an extension to dfiles
                    cfiles = ["{}.{}".format(os.path.splitext(df)[0], alg['cal_ext']) for df in dfiles]
                # calibrate
                uvc = UVCal()
                uvc.read_calfits(cfiles)
                uvutils.uvcalibrate(uvd, uvc)

            # get Tsys
            auto_Tsys = hp.utils.uvd_to_Tsys(uvd, alg['beam'], alg['output_Tsys_file'])

            # iterate over spectra and generate thermal noise errors
            for spec in spectra:
                # get uvp
                uvp = psc.get_pspec(group, spec)
                # get errorbars
                hp.utils.uvp_noise_error(uvp, auto_Tsys, err_type=alg['error_type'], precomp_P_N=alg['precomp_P_N'])
                # set uvp
                psc.set_pspec(group, spec, uvp, overwrite=True)

        except:
            hp.utils.log("\nNOISE_ERR errored with:", f=ef, tb=sys.exc_info(), verbose=params['verbose'])
            return 1

        return 0

    # launch noise calculation jobs
    failures = hp.utils.job_monitor(noise_err, [psc_fname], "NOISE_ERR", lf=lf, maxiter=params['maxiter'], verbose=params['verbose'])

    # print to log
    time = datetime.utcnow()
    hp.utils.log("\nFinished NOISE_ERR pipeline: {}\n{}".format(time, "-"*60), f=lf, verbose=params['verbose'])

#-------------------------------------------------------------------------------
# Run Bootstrap Pipeline
#-------------------------------------------------------------------------------
if params['run_bootstrap']:
    # start block
    time = datetime.utcnow()
    hp.utils.log("\n{}\nStarting BOOTSTRAP resampling pipeline: {}\n".format("-"*60, time), f=lf, verbose=params['verbose'])

    # ensure outfname is same as pspec if running both
    psc_fname = os.path.join(params['out_dir'], algs['bootstrap']['psc_name'])
    if params['run_pspec'] and (outfname != psc_fname):
        raise ValueError("bootstrap psc_fname {} doesn't equal pspec outfname {}".format(psc_fname, outfname))

    # open container
    psc = hp.PSpecContainer(psc_fname, mode='r')

    # get groups, close container
    groups = psc.groups()
    all_spectra = dict([(grp, [os.path.join(grp, s) for s in psc.spectra(grp)]) for grp in groups])
    del psc

    # define bootstrap function
    def bootstrap(i, groups=groups, ef=ef, alg=algs['bootstrap'], params=params, psc_fname=psc_fname):
        try:
            # get container
            psc = hp.PSpecContainer(psc_fname, mode='rw', keep_open=False, swmr=False)

            # get spectra
            grp = groups[i]
            spectra = all_spectra[grp]

            # run bootstrap
            hp.grouping.bootstrap_run(psc, spectra=spectra, time_avg=alg['time_avg'], Nsamples=alg['Nsamples'],
                                      seed=alg['seed'], normal_std=alg['normal_std'], robust_std=alg['robust_std'],
                                      cintervals=alg['cintervals'], keep_samples=alg['keep_samples'],
                                      bl_error_tol=alg['bl_error_tol'], overwrite=params['overwrite'], verbose=params['verbose'])

        except:
            hp.utils.log("\nBOOTSTRAP job {} errored with:".format(i), f=ef, tb=sys.exc_info(), verbose=params['verbose'])
            return 1

        return 0

    # launch bootstrap jobs
    failures = hp.utils.job_monitor(bootstrap, range(len(groups)), "BOOTSTRAP", lf=lf, maxiter=params['maxiter'], verbose=params['verbose'])

    # print failures if they exist
    if len(failures) > 0:
        hp.utils.log("\nSome BOOTSTRAP jobs failed after {} tries:\n{}".format(params['maxiter'], '\n'.join(["group {}: {}".format(i, str(groups[i])) for i in failures])), f=lf, verbose=params['verbose'])

    # print to log
    time = datetime.utcnow()
    hp.utils.log("\nFinished BOOTSTRAP pipeline: {}\n{}".format(time, "-"*60), f=lf, verbose=params['verbose'])
