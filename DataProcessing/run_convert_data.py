import pickle
import os,re
import sys
import time
from decimal import Decimal
import glob
import subprocess
import ROOT as r
import numpy as np

if __name__=="__main__":

    workDir = "/home/llavezzo/CMSSW_10_2_20/src/work/"

    dataDir = '/data/users/mcarrigan/condor/images_DYJetsM50/'
    files = []
    for filename in os.listdir(dataDir):
        if('.root' in filename and 'hist' in filename):
            fin = r.TFile(dataDir + filename)
            tree = fin.Get('trackImageProducer/tree')
            nEvents = tree.GetEntries()
            if(nEvents > 0): files.append(filename)
            del fin
            del tree
    np.save('fileslist',files)



    f = open('run.sub', 'w')
    submitLines = """

    Universe = vanilla
    +IsLocalJob = true
    Rank = TARGET.IsLocalSlot
    request_disk = 500MB
    request_memory = 2048MB
    request_cpus = 1
    executable              = run_wrapper.sh
    arguments               = $(PROCESS)
    log                     = /data/users/llavezzo/Logs/convert_data/log_$(PROCESS).log
    output                  = /data/users/llavezzo/Logs/convert_data/out_$(PROCESS).txt
    error                   = /data/users/llavezzo/Logs/convert_data/error_$(PROCESS).txt
    should_transfer_files   = Yes
    when_to_transfer_output = ON_EXIT
    transfer_input_files = {0}fileslist.npy, {0}run_wrapper.sh, {0}convert_data.py, {0}Infos.h
    getenv = true
    queue {1}

    """.format(workDir,len(files))

    f.write(submitLines)
    f.close()

    os.system('condor_submit run.sub')
