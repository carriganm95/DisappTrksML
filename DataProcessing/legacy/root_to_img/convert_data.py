import ROOT as r
from ROOT import gROOT
from ROOT.Math import XYZVector
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import math
import pandas as pd
import sys


gROOT.ProcessLine('.L Infos.h++')
gROOT.SetBatch()

# script arguments
process = int(sys.argv[1])
print("Process",process)

# name of the file to import
try:
    files = np.load('fileslist.npy')
    fileNum = files[process]
except:
    fileNum = process
fname = "hist_"+str(fileNum)+".root"



# output file tag
fOut = '0p25_'+str(fileNum)

##### config params #####
scaling = False
tanh_scaling = True
ZtoEE = False
res_eta = 40
res_phi = 40
eta_ub,eta_lb = 0.25,-0.25
phi_ub,phi_lb = 0.25,-0.25
#########################

# import data
dataDir = str(sys.argv[2])
fin = r.TFile(dataDir + fname)
tree = fin.Get('trackImageProducer/tree')
print("Opened file",fname)
nEvents = tree.GetEntries()
if(nEvents == 0):
    sys.exit("0 events found in file")
print("Added",nEvents)


# Convert coordinates from original mapping
# to range as specified in parameters
def convert_eta(eta):
    return int(round(((res_eta-1)*1.0/(eta_ub-eta_lb))*(eta-eta_lb)))

def convert_phi(phi):
    return int(round(((res_phi-1)*1.0/(phi_ub-phi_lb))*(phi-phi_lb)))

def type_to_channel(hittype):
    #none
    if(hittype == 0): return -1
    #ECAL (EE,EB)
    if(hittype == 1 or hittype == 2): return 0
    #ES
    if(hittype == 3): return 1 
    #HCAL
    if(hittype == 4): return 2
    #Muon (CSC,DT,RPC)
    if(hittype == 5 or hittype ==6 or hittype == 7): return 3

# Match electrons, muons
def check_track(track):
    if(abs(track.genMatchedID)==11 and abs(track.genMatchedDR) < 0.1): return 1
    #if(abs(track.genMatchedID)==11): return 1
    if(abs(track.genMatchedID)==13 and abs(track.genMatchedDR) < 0.1): return 2
    #if(abs(track.genMatchedID)==13): return 2
    return 0

def passesSelection(track):

    momentum = XYZVector(track.px, track.py, track.pz)
    eta = momentum.Eta()
    pt = math.sqrt(momentum.Perp2())

    if not abs(eta) < 2.4: return False
    if track.inGap: return False
    if not abs(track.dRMinJet) > 0.5: return False
    return True

def check_ZtoEE(event):
    count = 0
    pass_sel = False
    for iTrack, track in enumerate(event.tracks):
        print("Track ID: ", track.genMatchedID, track.genMatchedDR)
        #if(check_track(track) == 1): count += 1
	if(not passesSelection(track)): continue
	if(check_track(track) == 1): count += 1
    if count >= 2: pass_sel = True
    print("Number of electrons: ", count)
    return pass_sel

# images and infos split by gen matched type
images = [[],[],[]]
infos = [[],[],[]]
ID = 0

for iEvent,event in enumerate(tree):
    
    if(iEvent%1000==0): print(iEvent)
    
    nPV = event.nPV
    
    if(ZtoEE):   
       if(check_ZtoEE(event)==False): continue

    for iTrack,track in enumerate(event.tracks):

        if(not passesSelection(track)): continue
        
        matrix = np.zeros([res_eta,res_phi,4])

        momentum = XYZVector(track.px,track.py,track.pz)
        track_eta = momentum.Eta()
        track_phi = momentum.Phi()
 	
        hit_energy = 0
        max_hit = [-1, -10, -10]       
        for iHit,hit in enumerate(event.recHits):
        
            if(hit.detType != 3): 
                hit_energy += hit.energy
		    if(hit.energy > max_hit[0]):
                    max_hit[0] = hit.energy
                    max_hit[1] = hit.eta
                    max_hit[2] = hit.phi

            dEta = track_eta - hit.eta
            dPhi = track_phi - hit.phi
            # branch cut [-pi, pi)
            if abs(dPhi) > math.pi:
                dPhi -= round(dPhi / (2. * math.pi)) * 2. * math.pi

            if(dPhi > phi_ub or dPhi < phi_lb): continue
            if(dEta > eta_ub or dEta < eta_lb): continue

            dEta = convert_eta(dEta)
            dPhi = convert_phi(dPhi)

            channel = type_to_channel(hit.detType)
            if(channel == -1): continue

            if channel != 3: matrix[dEta,dPhi,channel] += hit.energy
            else: matrix[dEta][dPhi][channel] += 1
        
        track_DR = math.sqrt((track_eta-max_hit[1])**2 + (track_phi-max_hit[2])**2) 
        # scaling options
        if(scaling):
            scale = matrix[:,:,:3].max()
            scale_muons = matrix[:,:,3].max()
            if scale > 0: matrix[:,:,:3] = matrix[:,:,:3]*1.0/scale
            if scale_muons > 0: matrix[:,:,3] = matrix[:,:,3]*1.0/scale_muons
        if(tanh_scaling):
            matrix = np.tanh(matrix)
        matrix = matrix.flatten().reshape([matrix.shape[0]*matrix.shape[1]*matrix.shape[2],])  
        matrix = matrix.astype('float32')
        matrix = np.append(ID,matrix)
        
        genMatch = check_track(track)
        info = np.array([
            fileNum,
            ID,
            genMatch,
	    nPV,
            track.deltaRToClosestElectron,
            track.deltaRToClosestMuon,
            track.deltaRToClosestTauHad,
            track_eta,
            track_phi,
            track.genMatchedID,
            track.genMatchedDR,
	    track.pt,
            hit_energy,
            max_hit[0], 
            track_DR])

        images[genMatch].append(matrix)
        infos[genMatch].append(info)

        ID+=1

# check for errors before saving
nEvents = 0
for i in range(3):
    if(len(images[i])!=len(infos[i])): sys.exit("Images and infos don't match!")
    nEvents += len(images[i])
if(nEvents == 0): sys.exit("The output file is empty")

print(nEvents)

print("Saving to",fOut)
np.savez_compressed("images_bkg_"+fOut,images=images[0],infos=infos[0])
np.savez_compressed("images_e_"+fOut,images=images[1],infos=infos[1])
np.savez_compressed("images_m_"+fOut,images=images[2],infos=infos[2])
