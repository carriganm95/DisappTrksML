import os,re
import sys
import time
import numpy as np
import datetime

if __name__=="__main__":

    logdir = "/data/users/llavezzo/Logs/ae_genmuons_bkg/"

    params = [
        ["ae_genmuons_bkg/"]
    ]

    np.save('params.npy',params)
    njobs = len(params)

    if(not os.path.isdir(logdir)): os.mkdir(logdir)

    f = open('run.sub', 'w')
    submitLines = """
    Universe = vanilla
    +IsLocalJob = true
    Rank = TARGET.IsLocalSlot
    request_disk = 500MB
    request_memory = 2GB
    request_cpus = 4
    arguments               = $(PROCESS)
    executable              = train_wrapper.sh
    log                     = {0}log_$(PROCESS).log
    output                  = {0}out_$(PROCESS).txt
    error                   = {0}error_$(PROCESS).txt
    when_to_transfer_output = ON_EXIT
    getenv = true
    queue {1}
    """.format(logdir,njobs)

    f.write(submitLines)
    f.close()

    os.system('condor_submit run.sub')
