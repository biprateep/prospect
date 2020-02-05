"""
prospect.scripts.specview_cmx_frames
===================================

Write static html files from "[s/c/..]frame" files in CMX data
Don't know if this will be used for SV (once frames are superseeded by spectra)
"""

import os, sys, glob
import argparse
import numpy as np

import desispec.io
from desiutil.log import get_logger
from desitarget.targetmask import desi_mask
from desitarget.cmx.cmx_targetmask import cmx_mask
import desispec.spectra
import desispec.frame

from prospect import plotframes
from prospect import utils_specviewer
from prospect import myspecselect


def parse() :

    parser = argparse.ArgumentParser(description='Create exposure-based static html pages from CMX frames')
    parser.add_argument('--specprod_dir', help='Location of directory tree (data in specprod_dir/exposures/)', type=str)
    parser.add_argument('--exposure', help='Name of single exposure to be processed',type=str, default=None)
    parser.add_argument('--exposure_list', help='ASCII file providing list of exposures', type=str, default=None)
    parser.add_argument('--nspecperfile', help='Number of spectra in each html page', type=int, default=50)
    parser.add_argument('--webdir', help='Base directory for webpages', type=str)
    parser.add_argument('--nmax_spectra', help='Stop the production of HTML pages once a given number of spectra are done', type=int, default=None)
    parser.add_argument('--filetype', help='File category (currently sframe/cframe supported)', type=str, default='cframe')
    parser.add_argument('--mask', help='Select only objects with a given CMX_TARGET target mask', type=str, default=None)
    args = parser.parse_args()
    return args


def exposure_db(specprod_dir, filetype='cframe', expo_subset=None) :
    '''
    Returns list of [ expo, night, spectros ] available in specprod_dir/exposures tree, 
        with b,r,z frames whose name matches filetype
        spectros = list of spectrograph numbers from 0 to 9 (only those with 3 bands available are kept)
        expo_subset : list; if None, all available exposures will be included in the list
    '''
    exposures = list()
    if expo_subset is not None :
        # List of exposures (eg from an ASCII file) does not need zero-padding
        expo_subset = [ x.rjust(8, "0") for x in expo_subset]
    for night in os.listdir( os.path.join(specprod_dir,'exposures') ) :
        for expo in os.listdir( os.path.join(specprod_dir,'exposures',night) ) :
            if not os.path.isdir( os.path.join(specprod_dir,'exposures',night,expo) ) : continue
            if expo_subset is not None :
                if expo not in expo_subset : continue
            files_avail = os.listdir( os.path.join(specprod_dir,'exposures',night,expo) )
            spectro_avail = []
            for spectro_num in [str(i) for i in range(10)] :
                files_check = [ filetype+"-"+band+spectro_num+"-"+expo+".fits" for band in ['b','r','z'] ]
                if all(x in files_avail for x in files_check) :
                    spectro_avail.append(spectro_num)
            if len(spectro_avail) > 0 :
                exposures.append( [expo, night, spectro_avail] )
    return exposures



def main(args) :
    
    log = get_logger()
    specprod_dir = args.specprod_dir
    webdir = args.webdir
    assert args.filetype in ['sframe', 'cframe']
    
    expo_subset = None
    if args.exposure_list is not None :
        assert args.exposure is None
        expo_subset = np.loadtxt(args.exposure_list, dtype=str, comments='#')
    if args.exposure is not None :
        assert args.exposure_list is None
        expo_subset = [ args.exposure ]
    exposures = exposure_db(specprod_dir, filetype=args.filetype, expo_subset=expo_subset)

    if expo_subset is not None :
        tmplist = [ x[0] for x in exposures ]
        missing_expos = [ x for x in expo_subset if x.rjust(8, "0") not in tmplist ]
        for x in missing_expos : log.info("Missing exposure, cannot be processed : "+x)
    log.info(str(len(exposures))+" exposures to be processed")
        
    # Loop on exposures
    nspec_done = 0
    for exposure, night, spectrographs in exposures :
        
        log.info("Working on exposure "+exposure)
        fdir = os.path.join( specprod_dir, 'exposures', night, exposure )
        
        for spectrograph_num in spectrographs :
            frames = [ desispec.io.read_frame(os.path.join(fdir,args.filetype+"-"+band+spectrograph_num+"-"+exposure+".fits")) for band in ['b','r','z'] ]
            spectra = utils_specviewer.frames2spectra(frames)
            # Selection
            if args.mask != None :
                spectra = utils_specviewer.specviewer_selection(spectra, log=log,
                            mask=args.mask, mask_type='CMX_TARGET')
                if spectra == 0 : continue

            # Handle several html pages per exposure - sort by fiberid
            nspec_expo = spectra.num_spectra()
            log.info("Spectrograph number "+spectrograph_num+" : "+str(nspec_expo)+" spectra")
            sort_indices = np.argsort(frames[0].fibermap["FIBER"])
            nbpages = int(np.ceil((nspec_expo/args.nspecperfile)))
            for i_page in range(1,1+nbpages) :

                log.info(" * Page "+str(i_page)+" / "+str(nbpages))
                the_indices = sort_indices[(i_page-1)*args.nspecperfile:i_page*args.nspecperfile]            
                thespec = myspecselect.myspecselect(spectra, indices=the_indices)
                titlepage = "expo"+exposure+"_spectro"+spectrograph_num+"_"+str(i_page)
                html_dir = os.path.join(webdir,"exposures",exposure)
                if args.mask != None :
                    titlepage = args.mask+"_"+titlepage
                    html_dir = os.path.join(webdir, args.mask, exposure)
                if not os.path.exists(html_dir) : 
                    os.makedirs(html_dir)
                plotframes.plotspectra(thespec, with_noise=True, with_coaddcam=False, is_coadded=False, 
                            title=titlepage, html_dir=html_dir, mask_type='CMX_TARGET', with_thumb_only_page=True)
                
            # Stop running if needed, only once a full exposure is completed
            nspec_done += nspec_expo
            if args.nmax_spectra is not None :
                if nspec_done >= args.nmax_spectra :
                    log.info(str(nspec_done)+" spectra done : no other exposure will be processed")
                    break



