import pickle
import os,re
import sys
import time
from decimal import Decimal
import glob
import subprocess
import numpy as np

if __name__=="__main__":

    # dataDir = '/store/user/mcarrigan/disappearingTracks/images_higgsino_800GeV_10000cm_step3/'
    # outDir = '/store/user/llavezzo/disappearingTracks/AMSB_800GeV_10000cm_selection_fullSel_noEcaloCutV2/'
    dataDir = '/store/user/bfrancis/images_SingleEle2017F/'
    outDir = '/store/user/llavezzo/disappearingTracks/SingleEle2017F_selection_fullSel_noEcaloCutV2/'
    logDir = '/data/users/llavezzo/Logs/selection/'
    reprocessAllFiles = True

    if(not os.path.isdir(outDir)): os.mkdir(outDir)
    if(not os.path.isdir(logDir)): os.mkdir(logDir)

    alreadyProcessedFiles = []
    for filename in os.listdir(outDir):
        if('.root' in filename and 'hist' in filename):
            index1 = filename.find("_")
            index2 = filename.find(".")
            numFile = int(filename[index1+1:index2])
            alreadyProcessedFiles.append(numFile)
    files = []
    for filename in os.listdir(dataDir):
        if('.root' in filename and 'hist' in filename):
            index1 = filename.find("_")
            index2 = filename.find(".")
            numFile = int(filename[index1+1:index2])
            if(not reprocessAllFiles):
                if(numFile in alreadyProcessedFiles): continue
            files.append(numFile) 
    filelist = 'filelist.txt'
    np.savetxt(filelist,files)

    f = open('run.sub', 'w')
    submitLines = """
    Universe = vanilla
    +IsLocalJob = true
    Rank = TARGET.IsLocalSlot
    request_disk = 500MB
    request_memory = 2048MB
    request_cpus = 1
    executable              = wrapper.sh
    arguments               = $(PROCESS) {1} {2} {3}
    log                     = {4}log_$(PROCESS).log
    output                  = {4}out_$(PROCESS).txt
    error                   = {4}error_$(PROCESS).txt
    should_transfer_files   = Yes
    when_to_transfer_output = ON_EXIT
    transfer_input_files = {2}, wrapper.sh, makeSelectionReal.cpp, Infos.h
    getenv = true
    queue {0}
    """.format(len(files),dataDir,filelist,outDir, logDir)

    f.write(submitLines)
    f.close()

    os.system('condor_submit run.sub')
