"""
Script adapted from 
https://github.com/HERA-Team/H1C_IDR3_Power_Spectra/blob/main/SPOILERS/All_Epochs_Power_Spectra/H1C_IDR3_Power_Spectra.ipynb

Where possible, corresponding section headings from the original notebook,
e.g. 'Section 1.2: Imports', are referenced in comments for comparison
to the original notebook.
"""

# Section 1.2: Imports
# --------------------

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import ticker
import glob
import hera_pspec as hp
from pyuvdata import UVData, UVFlag
import scipy
import copy
import time
import simpleqe as sqe
import pickle
from argparse import ArgumentParser
import os
import time
import sys
# For this import to work, utils.py must be in the current working directory
sys.path.insert(1, "./")
import utils

script_start = time.time()


# Section 1.1: Settings
# ---------------------

parser = ArgumentParser()
parser.add_argument(
    "--prefix",
    type=str,
    default="",
    help="String appended to the front of all filenames.  Defaults to ''."
)
parser.add_argument(
    "--figures_folder",
    type=str,
    default="./figures",
    help="Where to save resultant figures.  Defaults to './figures'."
)
parser.add_argument(
    "--results_folder",
    type=str,
    default="./results",
    help="Where to save final Delta^2 uvpspec objects.  Defaults to "
         "'./results'."
)
parser.add_argument(
    "df",
    type=str,
    help="File containing final per-baseline power spectra."
)
parser.add_argument(
    "--no_xtalk_df",
    type=str,
    default="",
    help="File containing matching power spectra without cross-talk "
         "subtraction.  Defaults to ''."
)
parser.add_argument(
    "--wedge_buff_ns",
    type=float,
    default=300,
    help="Wedge buffer in nanoseconds.  Defaults to 300 ns."
)
parser.add_argument(
    "--sph_minimum_ew_distance",
    type=float,
    default=15,
    help="Minimum EW baseline separation in meters for spherical k binning.  "
         "Defaults to 15 m."
)
parser.add_argument(
    "--sph_minimum_bl_length",
    type=float,
    default=0,
    help="Minimum baseline length in meters for spherical k binning.  "
         "Defaults to 0 m."
)
parser.add_argument(
    "--sph_maximum_bl_length",
    type=float,
    default=1e100,
    help="Maximum baseline length in meters for spherical k binning.  "
         "Defaults to 1e100 m."
)
parser.add_argument(
    "--dk_multiplier",
    type=float,
    default=2,
    help="The size of each spherical k bin (Delta k) when multiplied by the "
         "natural k_parallel spacing."
)
parser.add_argument(
    "--k_start_multiplied",
    type=float,
    default=0.75,
    help="The center of the first spherical k bin in units of Delta k.  "
         "Defaults to 0.75."
)
parser.add_argument(
    "--HERA_data_dir",
    type=str,
    default="./HERA_data/",
    help="Path to directory containing 1) a 'hand_flags/' subdirectory of "
         "h5py-compatible 'hand flagging' files suffixed with '*hand_flags.h5'"
         " and 2) a single pyuvdata-compatible file used in the power spectrum"
         " analysis for metadata."
)
parser.add_argument(
    "--xtalk_flag_dict",
    type=str,
    default="./crosstalk_flagging_plot_variables.p",
    help="Path to pickled python dictionary containing delay-space flags for "
         "crosstalk systematics."
)
args = parser.parse_args()

prefix = args.prefix
figures_folder = args.figures_folder
results_folder = args.results_folder
df = args.df
no_xtalk_df = args.no_xtalk_df
wedge_buff_ns = args.wedge_buff_ns
sph_minimum_ew_distance = args.sph_minimum_ew_distance
sph_minimum_bl_length = args.sph_minimum_bl_length
sph_maximum_bl_length = args.sph_maximum_bl_length
dk_multiplier = args.dk_multiplier
k_start_multiplied = args.k_start_multiplied

if not os.path.exists(figures_folder):
    os.makedirs(figures_folder)
if not os.path.exists(results_folder):
    os.makedirs(results_folder)

# Hard coded parameters set by HERA
# overall signal loss corrections, per band
abscal_bias = {0: 1.0, 1: 1.0}  # this goes into data and errors  
other_bias = {0: 1.055, 1: 1.072}  # this goes into just data
# LST ranges of fields
lstcuts = [(-2.5, 0), # Field A
           (0.75, 2.75), # Field B
           (4, 6.25), # Field C
           (6.25, 9.25), # Field D
           (9.25, 14.75),  # Field E
          ]


# Section 2: Show Flags and Bands
# -------------------------------
print("Reading in flags...", end=" ")
start = time.time()

spw_ranges = [[176, 340], [535, 697]] # these can be found in the pspec histories
hand_flag_files = glob.glob(f"{args.HERA_data_dir}/hand_flags/*hand_flags.h5")
# JB needed to set run_check=False to get this sort to work.  I think there's an
# issue with backwards compatibility as these hand flag files were generated with
# an old version of pyuvdata (2.1.6.dev19+g6c831385) and the UKSRC environment
# uses pyuvdata 2.4.4
hand_flag_files = sorted(hand_flag_files, key=lambda f: np.mean(UVFlag(f, run_check=False).time_array))
# For the same reason as above, I had to set run_check=False here too
uvf = UVFlag(hand_flag_files, run_check=False)
lsts = np.unwrap(uvf.lst_array) * 12 / np.pi
while np.max(lsts) > 24:
    lsts -= 24
freqs = uvf.freq_array / 1e6

print(f"({time.time() - start:.1f} s)")


# Section 4: Load power spectrum container
# ----------------------------------------
print("Reading power spectra and applying corrections...", end=" ")
start = time.time()

# load get pspec container for cross-talk subtracted files
psc = hp.container.PSpecContainer(df, keep_open=False)
uvps_xtk, lens, angs, Nblps = utils.load_red_uvps(psc, 'stokespol', proj_EW_cut=14., spws=[0, 1], polpairs=['pI'])

# P_SN correction
for uvp in uvps_xtk:
    hp.utils.apply_P_SN_correction(uvp, P_SN='P_SN', P_N='P_N')

# apply bias correction
for uvp_xtk in uvps_xtk:
    utils.bias_correction(uvp_xtk, abscal_bias, other_bias)

print(f"({time.time() - start:.1f} s)")


# Section 7: Incoherent redundant (cylindrically) average
# -------------------------------------------------------
print("Performing redundant average...", end=" ")
start = time.time()

with open(args.xtalk_flag_dict, 'rb') as f:
    xtalk_flag_dict = pickle.load(f)
flag_neg_delays = xtalk_flag_dict['flag_neg_delays']
flag_pos_delays = xtalk_flag_dict['flag_pos_delays']
flag_all_delays = xtalk_flag_dict['flag_all_delays']
xtalk_dly_min = xtalk_flag_dict['xtalk_dly_min']
xtalk_dly_max = xtalk_flag_dict['xtalk_dly_max']

# weight redundant average by P_N, but propagate P_SN errorbar
history = "Bias Corrected:\ndata + error bias correction per spw {}\nother data-only bias correction per spw{}\n" \
          "Incoherent redundantly averaged, excluding auto-baseline-pairs, weighted by P_N" \
          "".format(abscal_bias, other_bias)
uvp_xtk_ravg = utils.red_avg(uvps_xtk, exclude_autos=True, error_weights='P_N', error_field=['P_SN'], add_to_history=history,
                             flag_all_delays=flag_all_delays, flag_pos_delays=flag_pos_delays, flag_neg_delays=flag_neg_delays)

print(f"({time.time() - start:.1f} s)")


# Section 8: Incoherent time average in LST fields
# ------------------------------------------------
print("Performing time average...", end=" ")
start = time.time()

# make LST cuts
fields_used = []
# uvp_xtk_tavg, uvp_tk_tavg = [], []
uvp_xtk_tavg = []
for field, lc in enumerate(lstcuts):
    # weight time-average by P_N
    history = "LST cut {} hours, average weighted by P_N".format(lc)
    lst_indexes = np.unique(uvp_xtk_ravg.lst_1_array, return_index=True)[1]
    lsts = np.array([uvp_xtk_ravg.lst_avg_array[i] for i in sorted(lst_indexes)])
    lsts_hrs = np.unwrap(lsts) * 12 / np.pi 
    while np.max(lsts_hrs) > 24:
        lsts_hrs -= 24
    
    lcut = (lsts_hrs >= lc[0]) & (lsts_hrs <= lc[1])
    if not np.any(lcut):
        continue
    fields_used.append(field)
    
    # average with cross-talk subtraction 
    u = uvp_xtk_ravg.select(lsts=lsts[lcut], inplace=False)
    u.average_spectra(time_avg=True, error_weights='P_N', error_field=['P_SN'], add_to_history=history)
    uvp_xtk_tavg.append(u)

print(f"({time.time() - start:.1f} s)")


# Section 8.1: Cylindrical Power Spectra and SNR
# ----------------------------------------------


# Section 8.2: Cylindrical Power Spectrum Noise
# ---------------------------------------------


# Section 9: Spherical average
# ----------------------------
print("Performing spherical average...", end=" ")
start = time.time()

# load a single dummy file
uvd = UVData()
uvd.read(f"{args.HERA_data_dir}/zen.grp1.of1.LST.0.64367.sum.LPXLTK.uvh5",
         bls=[(12, 13), (12, 12), (13, 13)], polarizations=['pI'])
uvd.select(times=uvd.time_array[:1])

# initialize pspecdata
beam = hp.PSpecBeamUV('/project/HERA_data/NF_HERA_IQ_power_beam_healpix128.fits')
ds = hp.PSpecData(dsets=[uvd], wgts=[None], beam=beam)
ds.Jy_to_mK()

# get spw
u = uvp_xtk_ravg
spw_ranges = u.get_spw_ranges()
spw_ranges = [np.where((uvd.freq_array[0] >= sr[0]-1e-9)&(uvd.freq_array[0] <= sr[1]+1e-9))[0] for sr in spw_ranges]
spw_ranges = [(sr[0], sr[-1]) for sr in spw_ranges]

# run pspec with parameters in file history
_u = ds.pspec([(12, 13)], [(12, 13)], (0, 0), u.get_polpairs(), input_data_weight=u.weighting,
             norm=u.norm, taper=u.taper, little_h='h^-3' in u.norm_units, spw_ranges=spw_ranges, store_cov=True,
             store_window=True, verbose=False, cov_model='autos')

# insert window functions into uvp
wf = _u.window_function_array[0]
for ut in uvp_xtk_tavg:
    ut.window_function_array = {k: np.repeat(_u.window_function_array[k], ut.Nblpairts, axis=0) for k in _u.spw_array}

# insert covariance: ad hoc b/c computing covariance for each blpair is too expensive, and noise cov is simple
norm_cov = {}
ut = uvp_xtk_tavg[0]
for spw in ut.spw_array:
    norm_cov[spw] = _u.cov_array_real[spw].squeeze()
    norm_cov[spw] /= _u.cov_array_real[spw].squeeze().diagonal().mean()

# Path to files necessary for exact window function computation
path_to_wf = '/project/HERA_data/delay_wf/'

# uvp_xtk_sph_1, uvp_tk_sph_1 = [], []
# uvp_xtk_sph_2, uvp_tk_sph_2 = [], []
uvp_xtk_sph_1 = []
uvp_xtk_sph_2 = []

# spherical average onto wide LOS k grid
# note that only covariance arrays will be reliable, as stats_arrays cannot account for bin2bin correlation
for band in range(2):
    print('\nBand {}'.format(band+1))
    # set dk separately for each band   
    dk = dk_multiplier * np.median(np.diff(uvp_xtk_tavg[0].get_kparas(band)))
    kbins = np.arange(k_start_multiplied * dk, 2.5, dk) # even spacing 

    # for uvp_xtk, uvp_tk, field in list(zip(uvp_xtk_tavg, uvp_tk_tavg, list('ABCDE'))): #loop over fields
    for uvp_xtk, field in list(zip(uvp_xtk_tavg, list('ABCDE'))):  # loop over fields
        print('* Field {}'.format(field))
        
        # deepcopy
        # u_xtk, u_tk = copy.deepcopy(uvp_xtk), copy.deepcopy(uvp_tk)
        u_xtk = copy.deepcopy(uvp_xtk)
        # make a covariance based on norm_cov, scaled by P_N and P_SN if detection is > 2 sigma
        utils.stat_to_cov(u_xtk, 'P_SN', norm_cov)
        # set P_N for all k_para modes below horizon delay + wedge_buff to large value
        u_xtk.set_stats_slice('P_N', 1e9 / scipy.constants.c, wedge_buff_ns, above=False, val=np.inf)
        # u_tk.set_stats_slice('P_N', 1e9 / scipy.constants.c, wedge_buff_ns, above=False, val=np.inf)

        # cut baselines by setting noise to infinity
        for blp, blvec in zip(u_xtk.get_blpairs(), u_xtk.get_blpair_blvecs()):
            cut = False
            if np.linalg.norm(blvec) < sph_minimum_bl_length:
                cut = True
            if np.linalg.norm(blvec) > sph_maximum_bl_length:
                cut = True
            if np.abs(blvec[0]) < sph_minimum_ew_distance:
                cut = True
            if cut:
                for spw in u_xtk.spw_array:
                    for pp in u_xtk.get_polpairs():
                        k = (spw, blp, pp)
                        # u_tk.set_stats('P_N', k, np.ones_like(u_tk.get_stats('P_N', k)) * np.inf)
                        u_xtk.set_stats('P_N', k, np.ones_like(u_xtk.get_stats('P_N', k)) * np.inf)

        # Get exact window functions
        # At this stage, their are not weighted. Weights are applied when calling 
        # hp.grouping.spherical_average with error_weights='P_N'
        filename = path_to_wf+'u_xtk_nw_field{}.hdf5'.format(field)
        if os.path.exists(filename):
            print(f'  Using window function found in {filename}')
            u_windows = hp.UVPSpec()
            u_windows.read_hdf5(filename)
            setattr(u_xtk, "window_function_array", u_windows.window_function_array)
            setattr(u_xtk, "window_function_kperp", u_windows.window_function_kperp)
            setattr(u_xtk, "window_function_kpara", u_windows.window_function_kpara)
            setattr(u_xtk, "exact_windows", True)           
            u_xtk.history += f'\n  Window functions replaced with those from {filename}\n\n'
        else:
            t0 = time.time()
            # compute window functions
            u_xtk.get_exact_window_functions(ftbeam_file=path_to_wf+'FT_beam_HERA_dipole', inplace=True,
                                             x_orientation=uvd.x_orientation, verbose=False)
            t1 = time.time()
            print('  Window function computation took %.1f mins.' %((t1-t0)/60))
            u_xtk.write_hdf5(filename, overwrite=False)

        # spherical average
        history = "average weighted by P_N, with {} ns wedge buffer exclusion".format(wedge_buff_ns)
        sph_xtk = hp.grouping.spherical_average(u_xtk, kbins, dk, error_weights='P_N', add_to_history=history)
        # sph_tk = hp.grouping.spherical_average(u_tk, kbins, dk, error_weights='P_N', add_to_history=history)
        # but wait: repeat with P_N scaled norm_cov to get proper P_N level (only needed if dk > 0.032)
        utils.stat_to_cov(u_xtk, 'P_N', norm_cov)

        sph2 = hp.grouping.spherical_average(u_xtk, kbins, dk, error_weights='P_N')
        for spw in sph_xtk.spw_array:
            sph_xtk.stats_array['P_N'][spw][0, :, 0] = np.sqrt(np.diagonal(sph2.cov_array_real[spw].squeeze()))
        # remove P_SN in stats array to avoid confusion
        sph_xtk.stats_array.pop('P_SN')
        # append
        if band == 0:            
            uvp_xtk_sph_1.append(sph_xtk)
            # uvp_tk_sph_1.append(sph_tk)
        else:
            uvp_xtk_sph_2.append(sph_xtk)
            # uvp_tk_sph_2.append(sph_tk)

print(f"({time.time() - start:.1f} s)")


# Section 9.2: Plot single \Delta^2(k) with window functions
# ----------------------------------------------------------

# convert to dsq
uvp_xtk_dsq_1 = []
for u in uvp_xtk_sph_1:
    uvp_xtk_dsq_1.append(u.convert_to_deltasq(inplace=False))
uvp_xtk_dsq_2 = []
for u in uvp_xtk_sph_2:
    uvp_xtk_dsq_2.append(u.convert_to_deltasq(inplace=False)) 

# set params
field = 2 # C

# WARNING: In the notebook, the k values are obtained for the second spectral
# window (spw = 1 as set in the line below).  These same k values are then used
# for all spectral windows in section 9.3 even though the different subbands in
# each spectral range will technically change the k values.  This behavior,
# whether or not it was intended, is being replicated here to stay true to
# what's in the original notebook from HERA.
spw = 1
uvp_xtk_dsq = [uvp_xtk_dsq_1, uvp_xtk_dsq_2][spw]
u = uvp_xtk_dsq[fields_used.index(field)]
print(u.exact_windows)
kp = u.get_kparas(spw)
ks = slice(np.argmin(np.abs(kp - 0.128)), None, 1)


# Section 9.3: Plot all \Delta^2(k) (real and imaginary)
# ------------------------------------------------------
print("Plotting all \\Delta^2(k)...", end=" ")
start = time.time()

xlim = .02, 2
ylim = 2e1, 2e6

# loop over real and imaginary power spectra
for func, c in [(np.real, 'deeppink'), (np.imag, 'royalblue')]:
    fig, axes = plt.subplots(2, len(uvp_xtk_dsq_1), figsize=(16, 8))
    fig.subplots_adjust(wspace=0.05, hspace=0.05)

    for i in range(2):
        uvp_xtk_dsq = [uvp_xtk_dsq_1, uvp_xtk_dsq_2][i]
        for j in range(len(uvp_xtk_dsq)):
            # get data
            ax = axes[i, j]
            u = uvp_xtk_dsq[j]
            spw = i
            
            # get power spectra and vertical error bars
            y = func(u.data_array[spw].squeeze().copy()[ks].copy())
            y[y < 0] *= 0
            yerr = np.sqrt(np.diagonal(u.cov_array_real[spw].squeeze()))[ks]
            pn = u.stats_array['P_N'][spw].real.squeeze()[ks]
            pn[pn <= 0] = np.nan
            kbins = u.get_kparas(spw)
            k = kbins[ks]
            z = u.cosmo.f2z(np.mean(u.get_spw_ranges()[spw][:2]))       

            # get x errorbars from window func
            x, xerr_low, xerr_hi = sqe.utils.interp_Wcdf(u.window_function_array[spw].squeeze(), kbins)
            xerr = np.array([xerr_low, xerr_hi]).T[ks]
            # plot data
            p1 = ax.errorbar(k, y, marker='o', ms=6, ls='',
                             yerr=yerr * 2, c=c, xerr=xerr.T, lw=1)
            p2, = ax.plot(k, pn, c='k', ls='--', lw=3)

            # handle subplot
            ax.tick_params(labelsize=16, direction='in', size=5)
            ax.tick_params(direction='in', size=3, which='minor')
            ax.set_yscale('log')
            ax.grid()
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            ax.text(0.05, 0.9, "Band {}, Field {}".format(i+1, "ABCDEFGHIJ"[fields_used[j]]), fontsize=18,
                    transform=ax.transAxes, bbox=dict(fc='w', ec='grey', alpha=0.9))
            if i == 0:
                ax.set_xticklabels([])
            else:
                ax.set_xlabel(r"$k\ [h\ {\rm Mpc}^{-1}]$", fontsize=22)
            if j == 0:
                if func == np.real:
                    ax.set_ylabel(r"$\Delta^2\ [{\rm mK}^2]$", fontsize=22)
                else:
                    ax.set_ylabel(r"Im$[\Delta^2]\ [{\rm mK}^2]$", fontsize=22)
            else:    
                ax.set_yticklabels([])
    
    plt.tight_layout()
    if func == np.imag:
        plt.savefig(f'{figures_folder}/{prefix}all_imaginary_limits.png', dpi=200)
    else:
        plt.savefig(f'{figures_folder}/{prefix}all_limits.png', dpi=200)

print(f"({time.time() - start:.1f} s)")


# Section 9.4: Plot all P(k) on a linear scale
# --------------------------------------------
print("Plotting all P(k)...", end=" ")
start = time.time()

fig, axes = plt.subplots(4, len(uvp_xtk_sph_1), figsize=(18, 12))
fig.subplots_adjust(wspace=0.05, hspace=0.05)

# set params
xlim = .02, 2.1

for i in range(4):
    ylim_set = False
    spw = i // 2
    uvp_xtk_sph = [uvp_xtk_sph_1, uvp_xtk_sph_2][spw]
    for j in range(len(uvp_xtk_sph)):
        # get data
        ax = axes[i, j]
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.0e'))
        u = uvp_xtk_sph[j]

        kp = u.get_kparas(spw)
        if i % 2 == 0:
            comp = np.real
            c = 'deeppink'
        else:
            comp = np.imag
            c = 'royalblue'
        y = comp(u.data_array[spw].squeeze().copy()).copy()
        yerr = np.sqrt(np.diagonal(u.cov_array_real[spw].squeeze()))
        pn = u.stats_array['P_N'][spw].real.squeeze()
        k = kp#ks[ks]
        
        # cut out bins with 0 or non-finite errors
        to_use = (pn > 0) | ~np.isfinite(pn)
        y = y[to_use]        
        yerr = yerr[to_use]
        pn = pn[to_use]
        k = k[to_use]
        if len(y) == 0:
            continue
                
        # plot data
        p1 = ax.errorbar(k, y, marker='o', ms=3, ls='',
                         yerr=yerr * 2, c=c, lw=.75)
        ax.fill_between(k, -2*pn, 2*pn, color='k', alpha=0.2, zorder=0)

        # handle subplot
        ax.tick_params(labelsize=16, direction='in', size=5)
        ax.tick_params(direction='in', size=3, which='minor')
        ax.grid()
        ax.set_xlim(xlim)
        if not ylim_set:
            ylim = -np.median(pn[np.isfinite(pn)])*3.2, np.median(pn[np.isfinite(pn)])*3.2
            ylim_set = True
        ax.set_ylim(ylim)
        ax.text(0.96, 0.9, "Band {} Field {}".format((i//2)+1, ("ABCDEFGHIJ"[fields_used[j]])), fontsize=16, ha='right',
                transform=ax.transAxes, bbox=dict(fc='w', ec='grey', alpha=0.9))
        if i < 3:
            ax.set_xticklabels([])
        else:
            ax.set_xlabel(r"$k\ [h\ {\rm Mpc}^{-1}]$", fontsize=16)
        if j == 0:
            if i % 2 == 0:
                ax.set_ylabel(r"$P(k)\ [{\rm mK}^2\ h^{-3}\ {\rm Mpc}^3]$", fontsize=16)
            else:
                ax.set_ylabel(r"Im$[P(k)]\ [{\rm mK}^2\ h^{-3}\ {\rm Mpc}^3]$", fontsize=16)
        else:
            ax.set_yticklabels([])

plt.tight_layout()
plt.savefig(f'{figures_folder}/{prefix}integrated_sph.png', dpi=200)

print(f"({time.time() - start:.1f} s)")


# Section 10: Save Results
# ------------------------
print("Writing results to disk...", end=" ")
start = time.time()

# results are saved to h5 files per-band and per-field
for spw in [0, 1]:
    uvp_xtk_sph = [uvp_xtk_sph_1, uvp_xtk_sph_2][spw]
    for field in range(len(uvp_xtk_sph)):
        uvp = copy.deepcopy(uvp_xtk_sph[field])
        uvp.select(spws=[spw])
        outfilename = f'{results_folder}/{prefix}Pofk_Band_{spw+1}_Field_{"ABCDEFGHIJ"[field]}.h5'
        uvp.write_hdf5(outfilename, overwrite=True)

    uvp_xtk_dsq = [uvp_xtk_dsq_1, uvp_xtk_dsq_2][spw]
    for field in range(len(uvp_xtk_dsq)):
        uvp = copy.deepcopy(uvp_xtk_dsq[field])
        uvp.select(spws=[spw])
        outfilename = f'{results_folder}/{prefix}Deltasq_Band_{spw+1}_Field_{"ABCDEFGHIJ"[field]}.h5'
        uvp.write_hdf5(outfilename, overwrite=True)

print(f"({time.time() - start:.1f} s)")

print("\nCalculations complete!")
print(f"Total time elapsed: {time.time() - script_start:.1f} s", end="\n\n")
