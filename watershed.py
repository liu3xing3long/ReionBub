import numpy as np
from scipy import ndimage
from skimage import measure, morphology, segmentation
from skimage.feature import peak_local_max
from tocmfastpy import *
from h_transform import *
import pylab as plt
import seaborn as sns
#possibly useful
#morphology.remove_small_objects

def local_maxima(arr, ionized, threshold_h=0.7, connectivity=2, try_loading=False, outfile='smoothed_11.npy', smoothing='hmax'):

    neighborhood = ndimage.morphology.generate_binary_structure(len(arr.shape), connectivity)
    maxima = peak_local_max(arr, labels=ionized, footprint=neighborhood, indices=False, exclude_border=False)
    if smoothing == 'hmax': #smoothing with h-max transform
        if try_loading:
            try:
                print "loading h_max_transform"
                smoothed_arr = np.load('smoothed.npy')
            except: 
                smoothed_arr = h_max_cpu(arr, neighborhood, maxima, threshold_h, mask=ionized, connectivity=connectivity)
                np.save(outfile, smoothed_arr)
        else:
            tarr = h_max_gpu(arr=arr,mask=ionized, maxima=maxima, h=threshold_h, n_iter=100)
            #import IPython; IPython.embed()
            smoothed_arr = h_max_cpu(tarr, neighborhood, maxima, threshold_h, mask=ionized, connectivity=2)
            np.save(outfile, smoothed_arr)
        maxima = peak_local_max(smoothed_arr, labels=ionized, footprint=neighborhood, indices=False, exclude_border=False)
    elif smoothing == 'bin':
        print 'Smoothing field with binary dilation'
        n_reg = 0
        m_reg = 1000
        while True:
            maxima = ionized & ndimage.binary_dilation(maxima, structure=neighborhood, iterations=1) #smoothing with binary dilation
            tmp_labels = measure.label(maxima, connectivity=connectivity)
            m_reg = len(measure.regionprops(tmp_labels))
            print m_reg
            if m_reg == n_reg: break
            n_reg = m_reg
    return maxima #np.where(detected_maxima)


def watershed_3d(image, connectivity=2, smoothing='hmax'):
    ionized = image == 1.
    Q = np.sum(ionized).astype(np.float32)/image.size #naive filling fraction
    ionized = ionized*morphology.remove_small_objects(ionized, 3)  #speeds up later process
    EDT = ndimage.distance_transform_edt(ionized)
    maxima = local_maxima(EDT.copy(), ionized, connectivity=connectivity, smoothing=smoothing)
    markers = measure.label(maxima, connectivity=connectivity)
    labels = morphology.watershed(-EDT, markers, mask=ionized)
    
    return labels, markers, EDT, Q

def _get_var(Q, logR):
    R = np.exp(logR)
    return -Q/4/np.pi/R**3
def get_size_dist(labels, Q, scale=1, log=True, n_bins=20):
    R = measure.regionprops(labels)
    R_eff = scale*np.array([r.equivalent_diameter/2 for r in R])
    #R_eff = (3*volumes/4/np.pi)**(1./3)
    #dn/dr*(4pi*r**4/3Q) = dn/d(r**(-3))

    if not log:
        hist,bins = np.histogram(R_eff, normed=True, bins=100)
    else:
        logR = np.log(R_eff)
        # var = -Q/4/np.pi/R_eff**3
        log_edges = np.linspace(np.min(logR)-1,np.max(logR)+1,n_bins)
        #var_edges = _get_var(Q, log_edges)
        hist,bin_edges = np.histogram(logR, bins=log_edges, normed=True)
        bws = (log_edges[1:]-log_edges[:-1])/2
        bins = np.exp((log_edges[1:]+log_edges[:-1])/2)
        hist *= 4*np.pi*bins**3/3/Q
        hist /= np.dot(hist, bws)
        
        #hist = hist/Q*4*np.pi*(bins)**3/3
    return hist, bins

def plot_zscroll_dist(fn1='watershed_z10.npz', fn2='watershed_z11.npz', fn3='watershed_z12.npz'):
    plt.figure()
    for fn in [fn1,fn2,fn3]:
        f = np.load(fn)
        hist, bins = get_size_dist(f['labels'], f['Q'], f['scale'])
        plt.plot(bins, hist, label=fn.split('.')[0].split('_')[1])
    plt.xscale('log')
    plt.xlabel('R(Mpc)')
    plt.ylabel(r'\frac{dP}{d\ln r}')
    plt.legend()
    sns.set_context("talk", font_scale=1.4)


def plot_dist(labels, scale=1):
    """
    scale is Mpc/pixel
    """
    R = measure.regionprops(labels)
    R_eff = scale*np.array([r.equivalent_diameter/2 for r in R])
    logR = np.log(R_eff)
    var = -Q/4/np.pi/R_eff**3
    log_edges = np.linspace(np.min(logR)-1,np.max(logR)+1,n_bins)
    var_edges = _get_var(Q, log_edges)
    hist,bin_edges = np.histogram(var, bins=var_edges, normed=True)
    bins = np.exp((log_edges[1:]+log_edges[:-1])/2)

    sns.distplot(R_eff, hist=False, bins=bins)

def watershed_21cmBox(path):
    box = boxio.readbox(path)
    return watershed_3d(box.box_data)

if __name__ == '__main__':
    #b1 = boxio.readbox('../pkgs/21cmFAST/TrialBoxes/xH_nohalos_z008.06_nf0.604669_eff20.0_effPLindex0.0_HIIfilter1_Mmin5.7e+08_RHIImax20_256_300Mpc')
    #b1 = boxio.readbox('../pkgs/21cmFAST/Boxes/xH_nohalos_z010.00_nf0.865885_eff20.0_effPLindex0.0_HIIfilter1_Mmin4.3e+08_RHIImax20_500_500Mpc')
    #DIR = '../pkgs/21cmFAST/Boxes/'
    #FILE = 'xH_nohalos_z010.00_nf0.873649_eff20.0_effPLindex0.0_HIIfilter1_Mmin4.3e+08_RHIImax30_500_250Mpc'
    #DIR = '/data2/21cmFast/lin0_logz10-35_box500_dim500/Boxes/'
    DIR = '/home/yunfanz/Data/21cmFast/Boxes/'
    #FILE = 'xH_nohalos_z010.00_nf0.145708_eff104.0_effPLindex0.0_HIIfilter1_Mmin4.3e+08_RHIImax30_500_500Mpc'
    #FILE = 'xH_nohalos_z012.00_nf0.761947_eff104.0_effPLindex0.0_HIIfilter1_Mmin3.4e+08_RHIImax30_500_500Mpc'
    FILE = 'xH_nohalos_z011.00_nf0.518587_eff104.0_effPLindex0.0_HIIfilter1_Mmin3.8e+08_RHIImax30_500_500Mpc'
    PATH = DIR+FILE
    #PATH = '/home/yunfanz/Data/21cmFast/Boxes/xH_nohalos_z010.00_nf0.881153_eff20.0_effPLindex0.0_HIIfilter1_Mmin4.3e+08_RHIImax20_400_100Mpc'
    b1 = boxio.readbox(PATH)
    d1 = 1 - b1.box_data#[::5,::5,::5]
    scale = float(b1.param_dict['dim']/b1.param_dict['BoxSize'])
    labels, markers, EDT, Q = watershed_3d(d1, smoothing='hmax')
    OUTFILE = b1.param_dict['basedir']+'/watershed_z'+str(int(np.round(b1.z)))+'.npz'
    print 'saving', OUTFILE
    np.savez(OUTFILE, Q=Q, scale=scale, labels=labels, markers=markers, EDT=EDT)


    hist, bins = get_size_dist(labels, Q, scale=scale)
    #import IPython; IPython.embed()
    # print 'computing bdt'
    # BDT = ndimage.distance_transform_bf(1-marker_ionized)
    # import pylab as plt
    # plt.figure()
    # plt.subplot(141)
    # plt.imshow(d1[128])
    # plt.subplot(142)
    # plt.imshow(EDT[128])
    # plt.subplot(143)
    # plt.imshow(labels[128])
    # plt.subplot(144)
    # plt.imshow(markers[128])

    # plt.figure()
    # plt.plot(bins[1:], hist)
    # plt.show()
