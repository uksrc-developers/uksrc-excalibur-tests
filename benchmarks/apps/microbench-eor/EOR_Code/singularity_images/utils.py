"""
utility functions for IO and plotting of H1C_IDR2 notebooks

Copied from https://github.com/HERA-Team/H1C_IDR3_Power_Spectra/blob/main/utils.py
"""
import numpy as np
import hera_pspec as hp
import simpleqe as sqe
from matplotlib import ticker
from scipy import stats


def wedge_plot(uvp, ax, spw, loglog=True, log10=True, fold=True, xlim=(5.0e-3, 6.1e-2), cmap='Spectral_r',
               ylim=(1.5e-2, 2.8e0), polpair=('pI', 'pI'), cbax=None, twiny=True, bl_label=True, twinx=True, dly_label=True, red_tol=0.1,
               component='real', fontsize=20, **kwargs):
    """
    Augmented wedge plotter, based off of hera_pspec.plot.delay_wedge

    Args:
        uvp : UVPSpec object
        **

    Returns:
       ax2, ax3 : axis objects of twin axes

    Note:
        To access colorbar, use ax.collections[0].colorbar 
    """
    freqs = uvp.get_spw_ranges(spw)[0][:2]
    z = uvp.cosmo.f2z(np.mean(uvp.get_spw_ranges(spw)[0][:2]))
    t2k = uvp.cosmo.tau_to_kpara(z, little_h=True) / 1e9

    hp.plot.delay_wedge(uvp, spw, polpair, log10=log10, ax=ax, fold=fold, rotate=True,
                        horizon_lines=False, red_tol=red_tol, colorbar=cbax is not None,
                        cbax=cbax, cmap=cmap, delay=False,
                        loglog=loglog, component=component, **kwargs)
    ax.tick_params(labelsize=16, size=8, direction='in', width=1, pad=10)
    ax.tick_params(which='minor', size=4, direction='in', width=1)
    if cbax is not None:
        cbar = ax.collections[0].colorbar
        cbar.ax.tick_params(labelsize=16)

    x = np.linspace(5, 140, 100)
    k = x * uvp.cosmo.bl_to_kperp(z)
    y = x / 2.99e8 * t2k * 1e9
    ax.plot(k, y + .0, color='grey', ls='--', lw=2.5)
    #ax.plot(k, y + np.diff(uvp.dly_array)[0] * 1e9 * t2k * 2, color='w', ls='--', lw=3)
    #ax.text(5.2e-3, 0.9e-1, "horizon", fontsize=18, rotation=0, c='w')

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_xlabel(r'$k_{\perp}\ [h\ {\rm Mpc}^{-1}$]', fontsize=fontsize)
    ax.set_ylabel(r'$k_{\parallel}\ [h\ {\rm Mpc}^{-1}$]', fontsize=fontsize)

    ax2 = None
    if twiny:
        ax2 = ax.twiny()
        if loglog:
            ax2.set_xscale('log')
        ax2.xaxis.set_major_formatter(ticker.StrMethodFormatter("{x:.1f}"))
        ax2.xaxis.set_minor_formatter(ticker.StrMethodFormatter("{x:.1f}"))
        ax2.set_xlim(*np.array(ax.get_xlim()) / uvp.cosmo.bl_to_kperp(z))
        ax2.tick_params(which='major', length=8, direction='in', width=1, labelsize=16)
        ax2.tick_params(which='minor', length=4, direction='in', width=1, labelsize=16)
        if bl_label:
            ax2.set_xlabel(r"$|b|$ [meters]", fontsize=fontsize, labelpad=10)
        else:
            ax2.set_xticklabels([])

    ax3 = None
    if twinx:
        ax3 = ax.twinx()
        if loglog:
            ax3.set_yscale('log')
        ax3.set_ylim(*np.array(ax.get_ylim()) / t2k)
        ax3.tick_params(which='major', length=8, direction='in', width=1, labelsize=16)
        ax3.tick_params(which='minor', length=4, direction='in', width=1)
        if dly_label:
            ax3.set_ylabel(r"$\tau$ [nanosec]", fontsize=fontsize, labelpad=10)
        else:
            ax3.set_yticklabels([])
        
    return ax2, ax3


def load_red_uvps(psc, groupname, proj_EW_cut=14, spec_name_end='dset1', **kwargs):
    """
    Load redundant uvpspec output from pspec_pipe.py

    Args:
        psc : PSpecContainer
        groupname : str
             psc groupname to load
        proj_EW_cut : float
            minimum projected East-West baseline cut [meters]
        spec_name_end : str or None
            If not None, only load spectra whose name ends in spec_name_end
        kwargs : dict
            kwargs to feed to psc.get_pspec()
    Returns:
        list
            list of UVPSpec objects
    """
    # load baselines w/ projected EW len > proj_EW_cut [meters]
    if spec_name_end is not None:
        spec = np.array([sp for sp in psc.spectra(groupname) if sp[-len(spec_name_end):] == spec_name_end])
    else: 
        spec = np.array([sp for sp in psc.spectra(groupname)])
    lens, angs = [float(sp[:3]) for sp in spec], [float(sp[5:8]) for sp in spec]
    proj_lens = [np.abs(l*np.cos(a*np.pi/180)) for l, a in zip(lens, angs)]
    keep = [i for i in range(len(proj_lens)) if (proj_lens[i] >= 14)]
    uvps = [psc.get_pspec(groupname, sp, **kwargs) for sp in spec[keep]]
    # correct for nans
    for uvp in uvps:
        for spw in uvp.spw_array:
            d = uvp.data_array[spw]
            d[np.isnan(d)] = 0
            if hasattr(uvp, 'stats_array'):
                for stat in uvp.stats_array:
                    e = uvp.stats_array[stat][spw].real
                    e[np.isnan(e)] = np.inf
                    uvp.stats_array[stat][spw] = e
    lens = [lens[i] for i in keep]
    angs = [angs[i] for i in keep]
    Nblps = [u.Nblpairs for u in uvps]
    return uvps, lens, angs, Nblps


def red_avg(uvps, exclude_autos=True, exclude_cross=False, error_weights='P_N',
            flag_all_delays={}, flag_pos_delays={}, flag_neg_delays={}, **kwargs):
    """
    Redundantly average and combine list of redundant group UVPSpec objects

    Args:
        uvps : list
            List of uvpspec, each holding a unique redundant baseline type
        exclude_autos : bool
            If True, exclude auto-baseline-pair from average
        exclude_cross : bool
            If True, exclude cross-baseline-pair from average
        error_weights: string, optional
            error_weights specify which kind of errors we use for weights during
            averaging power spectra. See UVPSpec.average_spectra() for more.
        flag_all_delays : dict
            Dictionary mapping power spectrum keys to bools for whether to completely
            flag that individual baseline by setting the error_weights to np.inf.
        flag_pos_delays : dict
            Dictionary mapping power spectrum keys to bools for whether to flag
            the individual baseline at all positive delays.
        flag_neg_delays : dict
            Dictionary mapping power spectrum keys to bools for whether to flag
            the individual baseline at all negative delays.            
        kwargs : dict
            kwargs for uvp.average_spectra()

    Returns:
        UVPSpec object
    """
    uvps_avg = []
    for uvp in uvps:
        blps = uvp.get_blpairs()
        if exclude_autos:
            blps = [blp for blp in blps if blp[0] != blp[1]]
        if exclude_cross:
            blps = [blp for blp in blps if blp[0] == blp[1]]
        if len(blps) > 0:
            u = uvp.select(blpairs=blps, inplace=False)            
            # apply delay-based flags
            for k in u.get_all_keys():
                error_array = u.get_stats(error_weights, k)
                if flag_all_delays.get(k, False):
                    error_array[:, :] = np.inf
                else:
                    if flag_pos_delays.get(k, False):
                        error_array[:, u.get_dlys(k[0]) > 0] = np.inf
                    if flag_neg_delays.get(k, False):
                        error_array[:, u.get_dlys(k[0]) < 0] = np.inf
                u.set_stats(error_weights, k, error_array)
            uvps_avg.append(u.average_spectra(blpair_groups=[u.get_blpairs()], inplace=False, 
                                              error_weights=error_weights, **kwargs))
    if len(uvps_avg) > 1:
        return hp.uvpspec.combine_uvpspec(uvps_avg, merge_history=False, verbose=False)
    else:
        return uvps_avg[0]


def bias_correction(uvp, total_bias=None, data_bias=None):
    """
    Apply correction factors to power spectra. operates inplace

    Args:
        uvp : UVPSpec object
        total_bias : dict
            bias correction to data and errors, e.g. abscal bias
            keys are spw integers, values are correction scalars
        data_bias : dict
            bias correction only to data, e.g. fringe-rate filtering
            keys are spw integers, values are correction scalars
    """
    for spw in uvp.spw_array:
        if total_bias is not None:
            uvp.data_array[spw] *= total_bias[spw]
            if hasattr(uvp, 'cov_array_real'):
                uvp.cov_array_real[spw] *= total_bias[spw]**2
                uvp.cov_array_imag[spw] *= total_bias[spw]**2
            if hasattr(uvp, 'stats_array'):
                for stat in uvp.stats_array:
                    uvp.stats_array[stat][spw] *= total_bias[spw]
        if data_bias is not None:
            uvp.data_array[spw] *= data_bias[spw]

def chisq(d, prec, m=None):
    """Compute chi-square
    
    Args:
        d : array-like
            data vector
        prec : 2d array
            precision matrix of data
        m : array-like
            mean to subtract
    """
    r = d
    if m is not None:
        r = d - m
    if r.ndim > 1:
        return np.array([chisq(_r, prec) for _r in r])
    return r @ prec @ r

def monte_carlo_chisq(cov, Ndata, N=10000):
    """Draw random realizations from covariance
    and compute chi-square

    Args:
        cov : 2d array
            covariance matrix to draw from
        Ndata : int
            Number of elements in the data vector
        N : int
            number of draws
    """
    Ndata = cov.shape[0]
    n = stats.multivariate_normal.rvs(np.zeros(Ndata), cov=cov, size=N)
    n_x2 = chisq(n, np.linalg.pinv(cov))
    return n_x2

def p_value(d, cov, m=None, N=10000, n_x2=None):
    # Monte Carlo sampling distribution of noise
    if n_x2 is None:
        n_x2 = monte_carlo_chisq(cov, N=N)
    else:
        N = len(n_x2)

    # compute chisq for d
    d_x2 = chisq(d, np.linalg.pinv(cov))

    # compute p-value
    exceed = n_x2 > d_x2
    d_p = np.sum(exceed) / N

    return d_x2, d_p, n_x2, exceed

def plot_pval(d_x2, n_x2, ax, bins=100, range=(0, 100), **kwargs):
    # histogram
    n, bins = np.histogram(n_x2, bins=bins, range=range, density=True)
    n = np.concatenate([[0], n])
    exceed = bins >= d_x2

    # plot
    ax.plot(bins, n, c='k', lw=2)
    ax.fill_between(bins[exceed], 0, n[exceed], **kwargs)

def lstcut(uvp, lst_range):
    """
    select out all LSTs in uvp within lst_range

    Args:
        uvp : UVPSpec object
        lst_range : len-2 tuple with lst ranges [hours]
    """
    lsts = np.unique(uvp.lst_avg_array)
    lsts_hrs = lsts * 12 / np.pi
    lcut = (lsts_hrs > lst_range[0]) & (lsts_hrs <= lst_range[1])
    return uvp.select(lsts=lsts[lcut], inplace=False)

def stat_to_cov(uvp, mode, norm_cov, sigma=None):
    """
    Take normalized covariance, scale by stat and insert as cov

    Note: only works on Npols=1 uvp objects
    
    Args:
        uvp : UVPSpec object
        mode : str, options=['P_N', 'P_SN', 'both']
            stats_array entry to scale norm_cov up by (squared)
            In 'both' mode, use P_SN for signal detections, and P_N otherwise
        norm_cov : dict
            keys are spw, values are normalized covariances (i.e. diagonal is 1.0)
            that are Nspwdlys x Nspwdlys
        sigma : float
            sigma of detections to use P_SN rather than P_N for mode='both'
    """
    # insert covariance: ad hoc b/c computing covariance for each blpair is too expensive, and noise cov is simple
    uvp.cov_array_real, uvp.cov_array_imag = {}, {}
    for spw in uvp.spw_array:
        # get the computed covariance, peak normalize it. real and imag are the same
        Ndlys = uvp.get_spw_ranges(spw)[0][-1]
        uvp.cov_array_real[spw] = np.zeros((uvp.Nblpairts, Ndlys, Ndlys, 1))
        uvp.cov_array_imag[spw] = np.zeros((uvp.Nblpairts, Ndlys, Ndlys, 1))
        # iterate over blp and get P_N, scale up normalized cov
        for i, blp in enumerate(uvp.get_blpairs()):
            tinds = uvp.blpair_to_indices(blp)
            key = (spw, blp, uvp.get_polpairs()[0])
            if mode == 'P_N':
                s = uvp.get_stats('P_N', key).real
            elif mode == 'P_SN':
                s = uvp.get_stats('P_SN', key).real
            elif mode == 'both':
                p_n = uvp.get_stats('P_N', key).real
                p_sn = uvp.get_stats('P_SN', key).real
                ratio = uvp.get_data(key).real / p_n.clip(0, 1e40)
                s = p_n.copy()
                exceed = ratio > sigma
                s[exceed] = p_sn[exceed].copy()
            for j in range(uvp.Ntimes):
                new_cov = np.diag(s[j]) @ norm_cov[spw] @ np.diag(s[j])
                new_cov[np.isnan(new_cov)] = 0.0
                uvp.cov_array_real[spw][tinds[j], :, :, 0] = new_cov.copy()
                uvp.cov_array_imag[spw][tinds[j], :, :, 0] = new_cov.copy()