#!/usr/bin/env python

import os
import sys
import math
import ctypes

from ROOT import TChain, TFile, TTree, TH1D, TH2D, TCanvas, THStack, gROOT, gStyle, TLegend, TGraph, TMarker

from tensorflow.keras.layers import concatenate

from DisappTrksML.DeepSets.architecture import *

arch = DeepSetsArchitecture()
arch.buildModel()
arch.load_model_weights('noReco_64.64.256_64.64.64.h5')

def calculateFidicualMaps(electron_payload, muon_payload, payload_suffix):

    fiducial_maps = {}

    for flavor in ['ele', 'muon']:
        fin = TFile(electron_payload if flavor is 'ele' else muon_payload, 'read')
        beforeVeto = fin.Get('beforeVeto' + payload_suffix)
        afterVeto = fin.Get('afterVeto' + payload_suffix)

        totalEventsBeforeVeto = 0
        totalEventsAfterVeto = 0
        nRegionsWithTag = 0

        # loop over all bins in eta-phi and count events before/after to calculate the mean inefficiency
        for xbin in range(1, beforeVeto.GetXaxis().GetNbins() + 1):
            for ybin in range(1, beforeVeto.GetYaxis().GetNbins() + 1):
                if beforeVeto.GetBinContent(xbin, ybin) > 0:
                    nRegionsWithTag += 1
                else:
                    continue
                totalEventsBeforeVeto += beforeVeto.GetBinContent(xbin, ybin)
                totalEventsAfterVeto  += afterVeto.GetBinContent(xbin, ybin)
        meanInefficiency = totalEventsAfterVeto / totalEventsBeforeVeto

        # now with the mean, calculate the standard deviation as stdDev^2 = 1/(N-1) * sum(inefficiency - meanInefficiency)^2
        stdDevInefficiency = 0

        efficiency = afterVeto.Clone(flavor + '_efficiency')
        efficiency.SetDirectory(0)
        efficiency.Divide(beforeVeto)

        for xbin in range(1, efficiency.GetXaxis().GetNbins() + 1):
            for ybin in range(1, efficiency.GetYaxis().GetNbins() + 1):
                if beforeVeto.GetBinContent(xbin, ybin) == 0:
                    continue
                thisInefficiency = efficiency.GetBinContent(xbin, ybin)
                stdDevInefficiency += (thisInefficiency - meanInefficiency)**2

        if nRegionsWithTag < 2:
            print 'Only ', nRegionsWithTag, ' regions with a tag lepton exist, cannot calculate fiducial map!!!'
            return hotSpots

        stdDevInefficiency /= nRegionsWithTag - 1
        stdDevInefficiency = math.sqrt(stdDevInefficiency)

        for xbin in range(1, efficiency.GetXaxis().GetNbins() + 1):
            for ybin in range(1, efficiency.GetYaxis().GetNbins() + 1):
                if beforeVeto.GetBinContent(xbin, ybin) == 0:
                    continue
                efficiency.SetBinContent(xbin, ybin, efficiency.GetBinContent(xbin, ybin) - meanInefficiency)
        efficiency.Scale(1. / stdDevInefficiency)

        fiducial_maps[flavor] = efficiency

    return fiducial_maps

def fiducialMapSigma(track, fiducial_maps):
    maxSigma = -999.

    iBin = fiducial_maps['ele'].GetXaxis().FindBin(track.eta)
    jBin = fiducial_maps['ele'].GetYaxis().FindBin(track.phi)

    for i in range(iBin-1, iBin+2):
        if i > fiducial_maps['ele'].GetNbinsX() or i < 0: continue
        for j in range(jBin-1, jBin+2):
            if j > fiducial_maps['ele'].GetNbinsY() or j < 0: continue

            dEta = track.eta - fiducial_maps['ele'].GetXaxis().GetBinCenter(i)
            dPhi = track.phi - fiducial_maps['ele'].GetYaxis().GetBinCenter(j)

            if dEta*dEta + dPhi*dPhi > 0.05*0.5:
                continue
            
            if fiducial_maps['ele'].GetBinContent(i, j) > maxSigma:
                maxSigma = fiducial_maps['ele'].GetBinContent(i, j)

            if fiducial_maps['muon'].GetBinContent(i, j) > maxSigma:
                maxSigma = fiducial_maps['muon'].GetBinContent(i, j)

    return maxSigma

def signalSelection(event, fiducial_maps, fiducial_map_cut=-1):

    eventPasses = (event.firesGrandOrTrigger == 1 and
                   event.passMETFilters == 1 and
                   event.numGoodPVs >= 1 and
                   event.metNoMu > 120 and
                   event.numGoodJets >= 1 and
                   event.dijetDeltaPhiMax <= 2.5 and
                   abs(event.leadingJetMetPhi) > 0.5)

    trackPasses = [False] * len(event.tracks)

    if not eventPasses:
        return eventPasses, trackPasses

    for i, track in enumerate(event.tracks):
        if (not abs(track.eta) < 2.1 or
            not track.pt > 55 or
            track.inGap == 0 or
            not (track.phi < 2.7 or track.eta < 0 or track.eta > 1.42)): # 2017 eta-phi low efficiency
            continue

        if fiducial_map_cut > 0:
            if fiducialMapSigma(track, fiducial_maps) > fiducial_map_cut:
                continue

        if (not track.dRMinBadEcalChannel >= 0.05 or
            not track.nValidPixelHits >= 4 or
            not track.nValidHits >= 4 or
            not track.missingInnerHits == 0 or
            not track.missingMiddleHits == 0 or
            not track.trackIso / track.pt < 0.05 or
            not abs(track.d0) < 0.02 or
            not abs(track.dz) < 0.5 or
            not abs(track.dRMinJet) > 0.5 or
            not abs(track.deltaRToClosestElectron) > 0.15 or
            not abs(track.deltaRToClosestMuon) > 0.15 or
            not abs(track.deltaRToClosestTauHad) > 0.15 or
            not track.ecalo < 10 or
            not track.missingOuterHits >= 3):
            continue

        trackPasses[i] = True

    return (True in trackPasses), trackPasses

def fakeBackgroundSelection(event, fiducial_maps, fiducial_map_cut=-1):
    eventPasses = (event.passMETFilters == 1)
    trackPasses = [False] * len(event.tracks)

    if not eventPasses:
        return eventPasses, trackPasses, trackPassesVeto

    for i, track in enumerate(event.tracks):
        if (not abs(track.eta) < 2.1 or
            not track.pt > 30 or
            track.inGap == 0 or
            not (track.phi < 2.7 or track.eta < 0 or track.eta > 1.42)): # 2017 eta-phi low efficiency
            continue

        if fiducial_map_cut > 0:
            if fiducialMapSigma(track, fiducial_maps) > fiducial_map_cut:
                continue

        if (not track.dRMinBadEcalChannel >= 0.05 or
            not track.nValidPixelHits >= 4 or
            not track.nValidHits >= 4 or
            not track.missingInnerHits == 0 or
            not track.missingMiddleHits == 0 or
            not track.trackIso / track.pt < 0.05 or
            # d0 sideband
            not abs(track.d0) >= 0.05 or
            not abs(track.d0) < 0.5 or
            not abs(track.dz) < 0.5 or
            not abs(track.dRMinJet) > 0.5 or
            not abs(track.deltaRToClosestElectron) > 0.15 or
            not abs(track.deltaRToClosestMuon) > 0.15 or
            not abs(track.deltaRToClosestTauHad) > 0.15 or
            not track.ecalo < 10 or
            not track.missingOuterHits >= 3):
            continue

        trackPasses[i] = True

    return (True in trackPasses), trackPasses

def leptonBackgroundSelection(event, fiducial_maps, lepton_type, fiducial_map_cut=-1):

    eventPasses = (event.passMETFilters == 1)
    trackPasses = [False] * len(event.tracks)
    trackPassesVeto = [False] * len(event.tracks)

    if not eventPasses:
        return eventPasses, trackPasses, trackPassesVeto

    for i, track in enumerate(event.tracks):

        if (not abs(track.eta) < 2.1 or
            not track.pt > 30 or
            track.inGap == 0 or
            not (track.phi < 2.7 or track.eta < 0 or track.eta > 1.42)): # 2017 eta-phi low efficiency
            continue

        if fiducial_map_cut > 0:
            if fiducialMapSigma(track, fiducial_maps) > fiducial_map_cut:
                continue

        if (lepton_type == 'electrons' and not track.isTagProbeElectron == 1):
            continue
        if (lepton_type == 'muons' and not track.isTagProbeMuon == 1):
            continue

        if (not track.dRMinBadEcalChannel >= 0.05 or
            not track.nValidPixelHits >= 4 or
            not track.nValidHits >= 4 or
            not track.missingInnerHits == 0 or
            not track.missingMiddleHits == 0 or
            not track.trackIso / track.pt < 0.05 or
            not abs(track.d0) < 0.02 or
            not abs(track.dz) < 0.5 or
            not abs(track.dRMinJet) > 0.5 or
            not abs(track.deltaRToClosestTauHad) > 0.15):
            continue

        if (lepton_type == 'electrons' and not abs(track.deltaRToClosestMuon) > 0.15):
            continue
        if (lepton_type == 'muons' and (not abs(track.deltaRToClosestElectron) > 0.15 or not track.ecalo < 10)):
            continue

        trackPasses[i] = True

        if lepton_type == 'electrons':
            if (abs(track.deltaRToClosestElectron) > 0.15 and
                track.ecalo < 10 and
                track.missingOuterHits >= 3):
                trackPassesVeto[i] = True
        if lepton_type == 'muons':
            if (abs(track.deltaRToClosestMuon) > 0.15 and
                track.missingOuterHits >= 3):
                trackPassesVeto[i] = True

    return (True in trackPasses), trackPasses, trackPassesVeto

def printEventInfo(event, track):
    print 'EVENT INFO'
    print 'Trigger:', event.firesGrandOrTrigger
    print 'MET filters:', event.passMETFilters
    print 'Num good PVs (>=1):', event.numGoodPVs
    print 'MET (no mu) (>120):', event.metNoMu
    print 'Num good jets (>=1):', event.numGoodJets
    print 'max dijet dPhi (<=2.5):', event.dijetDeltaPhiMax
    print 'dPhi(lead jet, met no mu) (>0.5):', abs(event.leadingJetMetPhi)
    print
    print 'TRACK INFO'
    print '\teta (<2.1):', abs(track.eta)
    print '\tpt (>55):', track.pt
    print '\tIn gap (false):', track.inGap
    print '\tNot in 2017 low eff. region (true):', (track.phi < 2.7 or track.eta < 0 or track.eta > 1.42)
    print '\tmin dR(track, bad ecal channel) (>= 0.05):', track.dRMinBadEcalChannel
    print '\tnValidPixelHits (>=4):', track.nValidPixelHits
    print '\tnValidHits (>=4):', track.nValidHits
    print '\tmissing inner hits (==0):', track.missingInnerHits
    print '\tmissing middle hits (==0):', track.missingMiddleHits
    print '\ttrackIso/pt (<0.05):', track.trackIso / track.pt
    print '\td0 (<0.02):', abs(track.d0)
    print '\tdz (<0.5):', abs(track.dz)
    print '\tmin dR(track, jet) (>0.5):', abs(track.dRMinJet)
    print '\tmin dR(track, ele) (>0.15):', abs(track.deltaRToClosestElectron)
    print '\tmin dR(track, muon) (>0.15):', abs(track.deltaRToClosestMuon)
    print '\tmin dR(track, tauHad) (>0.15):', abs(track.deltaRToClosestTauHad)
    print '\tecalo (<10):', track.ecalo
    print '\tmissing outer hits (>=3):', track.missingOuterHits
    print
    print '\tisTagProbeElectron:', track.isTagProbeElectron
    print '\tisTagProbeMuon:', track.isTagProbeMuon

def processDataset(dataset, inputDir):
    if os.path.exists('output_' + dataset + '.root'):
        return

    payload_dir = os.environ['CMSSW_BASE'] + '/src/OSUT3Analysis/Configuration/data/'
    fiducial_maps = calculateFidicualMaps(payload_dir + 'electronFiducialMap_2017_data.root', 
                                          payload_dir + 'muonFiducialMap_2017_data.root', 
                                          '' if dataset.startswith('higgsino') else '_2017F')

    h_disc  = TH2D('disc', 'disc:discriminant:nLayers', 3000, 0, 1, 3, 4, 7)
    h_sigma = TH2D('sigma', 'sigma:sigma:nLayers', 3000, 0, 30, 3, 4, 7)
    h_sigma_afterCuts = TH2D('sigma_afterCuts', 'sigma_afterCuts:sigma:nLayers', 3000, 0, 30, 3, 4, 7)

    chain = TChain('trackImageProducer/tree')
    chain.Add(inputDir)

    nEvents = chain.GetEntries()
    print '\nAdded', nEvents, 'events for dataset type:', dataset, '\n'

    for iEvent, event in enumerate(chain):
        if iEvent % 10000 == 0:
            print '\tEvent', iEvent, '/', nEvents, '...'

        if dataset.startswith('higgsino'):
            eventPasses, trackPasses = signalSelection(event, fiducial_maps)
        elif dataset == 'fake':
            eventPasses, trackPasses = fakeBackgroundSelection(event, fiducial_maps)
        else:
            eventPasses, trackPasses, trackPassesVeto = leptonBackgroundSelection(event, fiducial_maps, dataset)

        if not eventPasses: continue

        for iTrack, track in enumerate(event.tracks):
            if not trackPasses[iTrack]: continue

            sigma = fiducialMapSigma(track, fiducial_maps)
            h_sigma.Fill(sigma, track.nLayersWithMeasurement)

            if dataset in ['electrons', 'muons'] and not trackPassesVeto[iTrack]: continue
            
            h_disc.Fill(arch.evaluate_model(event, track), track.nLayersWithMeasurement)
            h_sigma_afterCuts.Fill(sigma, track.nLayersWithMeasurement)

    outputFile = TFile('output_' + dataset + '.root', 'recreate')
    h_disc.Write()
    h_sigma.Write()
    h_sigma_afterCuts.Write()
    outputFile.Close()

def getROC(h_ele, h_mu, h_fake, h_signal, nlayers):
    ibin = h_ele.GetYaxis().FindBin(nlayers)

    h1d_bkg = h_ele.ProjectionX('roc1d_ele_'      + str(nlayers), ibin, ibin if nlayers < 6 else -1)
    h1d_bkg.Add(h_mu.ProjectionX('roc1d_mu_'      + str(nlayers), ibin, ibin if nlayers < 6 else -1))
    h1d_bkg.Add(h_fake.ProjectionX('roc1d_fake_'  + str(nlayers), ibin, ibin if nlayers < 6 else -1))
    h1d_sig  = h_signal.ProjectionX('roc1d_sig_'  + str(nlayers), ibin, ibin if nlayers < 6 else -1)

    n_bkg = h1d_bkg.Integral()
    n_sig = h1d_sig.Integral()

    graph = TGraph()

    best_sOverRootB = 1
    best_cut = h1d_bkg.GetBinLowEdge(h1d_bkg.GetNbinsX() + 1)
    best_cut_x = best_cut_y = 1

    i = 0
    for j in reversed(range(h1d_bkg.GetNbinsX())):
        n_pass_bkg = h1d_bkg.Integral(1, j+1)
        n_pass_sig = h1d_sig.Integral(1, j+1)

        graph.SetPoint(i, n_pass_bkg / n_bkg if n_bkg > 0 else 0, n_pass_sig / n_sig if n_sig > 0 else 0)
        i += 1

        if n_pass_bkg > 0 and n_sig > 0 and n_bkg > 0:
            sOverRootB = n_pass_sig / n_sig / math.sqrt(n_pass_bkg / n_bkg)
            if sOverRootB > best_sOverRootB:
                best_sOverRootB = sOverRootB
                best_cut = h1d_bkg.GetBinLowEdge(j+2)
                best_cut_x = n_pass_bkg / n_bkg
                best_cut_y = n_pass_sig / n_sig

    return (graph, best_cut, best_cut_x, best_cut_y)

def getWP(h_ele, h_ele_sigma, h_mu, h_mu_sigma, h_fake, h_fake_sigma, h_signal, h_signal_sigma, nlayers):
    ibin = h_ele.GetYaxis().FindBin(nlayers)

    bkg_ele  = h_ele.ProjectionX   ('ele_'  + str(nlayers), ibin, ibin if nlayers < 6 else -1)
    bkg_muon = h_mu.ProjectionX  ('muon_' + str(nlayers), ibin, ibin if nlayers < 6 else -1)
    bkg_fake = h_fake.ProjectionX  ('fake_' + str(nlayers), ibin, ibin if nlayers < 6 else -1)
    signal   = h_signal.ProjectionX('sig_'  + str(nlayers), ibin, ibin if nlayers < 6 else -1)

    bkg_ele_sigma  = h_ele_sigma.ProjectionX   ('ele_'  + str(nlayers), ibin, ibin if nlayers < 6 else -1)
    bkg_muon_sigma = h_mu_sigma.ProjectionX  ('muon_' + str(nlayers), ibin, ibin if nlayers < 6 else -1)
    bkg_fake_sigma = h_fake_sigma.ProjectionX  ('fake_' + str(nlayers), ibin, ibin if nlayers < 6 else -1)
    signal_sigma   = h_signal_sigma.ProjectionX('sig_'  + str(nlayers), ibin, ibin if nlayers < 6 else -1)

    ibin = bkg_ele.FindBin(0.2)
    n_pass_bkg = bkg_ele.Integral(1, ibin) + bkg_muon.Integral(1, ibin) + bkg_fake.Integral(1, ibin)
    n_pass_signal = signal.Integral(1, ibin)

    ibin = bkg_ele_sigma.FindBin(2.0)
    n_pass_bkg_sigma = bkg_ele_sigma.Integral(0, ibin) + bkg_muon_sigma.Integral(0, ibin) + bkg_fake_sigma.Integral(0, ibin)
    n_pass_signal_sigma = signal_sigma.Integral(0, ibin)

    change_bkg = n_pass_bkg / n_pass_bkg_sigma if n_pass_bkg_sigma > 0 else 1.0
    change_signal = n_pass_signal / n_pass_signal_sigma if n_pass_signal_sigma > 0 else 1.0

    return (change_bkg, change_signal)

def plotStack(h_ele, h_muon, h_fake, h_signal, nlayers, output_prefix, canvas, rebin=-1):
    ibin = h_ele.GetYaxis().FindBin(nlayers)

    bkg_ele  = h_ele.ProjectionX   ('ele_'  + str(nlayers), ibin, ibin if nlayers < 6 else -1)
    bkg_muon = h_muon.ProjectionX  ('muon_' + str(nlayers), ibin, ibin if nlayers < 6 else -1)
    bkg_fake = h_fake.ProjectionX  ('fake_' + str(nlayers), ibin, ibin if nlayers < 6 else -1)
    signal   = h_signal.ProjectionX('sig_'  + str(nlayers), ibin, ibin if nlayers < 6 else -1)

    bkg_ele.SetFillStyle(1001)
    bkg_ele.SetFillColor(400 - 7) # kYellow-7
    bkg_ele.SetLineColor(1)
    bkg_ele.Add(bkg_muon)
    bkg_ele.Add(bkg_fake)

    bkg_muon.SetFillStyle(1001)
    bkg_muon.SetFillColor(632) # kRed
    bkg_muon.SetLineColor(1)
    bkg_muon.Add(bkg_fake)

    bkg_fake.SetFillStyle(1001)
    bkg_fake.SetFillColor(8) # ~green
    bkg_fake.SetLineColor(1)
        
    signal.SetLineColor(1)
    signal.SetLineWidth(3)

    if rebin > 0:
        bkg_ele.Rebin(rebin)
        bkg_muon.Rebin(rebin)
        bkg_fake.Rebin(rebin)
        signal.Rebin(rebin)

    bkg_ele.GetXaxis().SetTitle('Discriminant')
    bkg_ele.GetYaxis().SetTitle('Events')

    bkg_ele.Draw('hist')
    bkg_muon.Draw('hist same')
    bkg_fake.Draw('hist same')
    signal.Draw('same')

    legend = TLegend(0.55, 0.7, 0.85, 0.85)
    legend.SetBorderSize(0)
    legend.SetFillColor(0)
    legend.SetFillStyle(0)
    legend.SetTextFont(42)

    legend.AddEntry(bkg_ele, 'Electrons', 'F')
    legend.AddEntry(bkg_muon, 'Muons', 'F')
    legend.AddEntry(bkg_fake, 'Fakes', 'F')
    legend.AddEntry(signal, 'Higgsino 300_1000', 'L')
    legend.Draw('same')

    canvas.SaveAs(output_prefix + '_' + str(nlayers) + '.pdf')

def printChanges(label, h_sigma, h_disc, disc_cut, nlayers, iClone):
    ibin = h_sigma.GetYaxis().FindBin(nlayers)
    iClone += 1

    h_sigma_proj = h_sigma.ProjectionX('sigma_proj_' + str(iClone), ibin, ibin if nlayers < 6 else -1)
    h_disc_proj  = h_disc.ProjectionX( 'disc_proj_' + str(iClone), ibin, ibin if nlayers < 6 else -1)

    n_pass_sigma = h_sigma_proj.Integral(0, h_sigma_proj.FindBin(2.0))
    n_pass_disc = h_disc_proj.Integral(0, h_disc_proj.FindBin(disc_cut))

    eff_sigma = n_pass_sigma / h_sigma_proj.Integral() if h_sigma_proj.Integral() > 0 else 0
    eff_disc = n_pass_disc / h_disc_proj.Integral() if h_disc_proj.Integral() > 0 else 0

    eff_ratio = eff_disc / eff_sigma if eff_sigma > 0 else 0

    print label, eff_ratio

    return label + ' ' + str(eff_ratio)

def analyze(datasets, inputDir='.'):

    gROOT.SetBatch()
    gStyle.SetOptStat(0)
    gStyle.SetOptTitle(0)

    canvas = TCanvas("c1", "c1", 800, 800)

    input_ele = TFile(inputDir + '/output_electrons.root', 'read')
    input_muon = TFile(inputDir + '/output_muons.root', 'read')
    input_fake = TFile(inputDir + '/output_fake.root', 'read')

    h_disc_ele = input_ele.Get('disc')
    h_disc_muon = input_muon.Get('disc')
    h_disc_fake = input_fake.Get('disc')

    h_sigma_ele = input_ele.Get('sigma')
    h_sigma_muon = input_muon.Get('sigma')
    h_sigma_fake = input_fake.Get('sigma')

    h_disc_signal = {}
    h_sigma_signal = {}
    for dataset in datasets:
        if not dataset.startswith('higgsino'): continue
        fin = TFile(inputDir + '/output_' + dataset + '.root', 'read')

        h_disc = fin.Get('disc')
        h_sigma = fin.Get('sigma')

        h_disc.SetDirectory(0)
        h_sigma.SetDirectory(0)

        h_disc_signal[dataset] = h_disc
        h_sigma_signal[dataset] = h_sigma

        fin.Close()

    roc_curves = { 'disc_%d_%s' % (i, sig) : getROC(h_disc_ele, h_disc_muon, h_disc_fake, h_disc_signal[sig], i) for i in [4, 5, 6] for sig in h_disc_signal }
    roc_curves.update(
        { 'sigma_%d_%s' % (i, sig) : getROC(h_sigma_ele, h_sigma_muon, h_sigma_fake, h_sigma_signal[sig], i) for i in [4, 5, 6] for sig in h_disc_signal }
    )

    fout = TFile('durp.root', 'recreate')
    for curve_name in roc_curves:
        roc_curves[curve_name][0].Write(curve_name)
        print 'Optimal cut for', curve_name, '=', roc_curves[curve_name][1]
        m = TMarker(roc_curves[curve_name][2], roc_curves[curve_name][3], 29)
        m.Write(curve_name + '_optimal')
    fout.Close()

    for i in [4, 5, 6]:
        plotStack(h_disc_ele, h_disc_muon, h_disc_fake, h_disc_signal['higgsino_300_1000'], i, 'discriminant', canvas, rebin=5)
        plotStack(h_sigma_ele, h_sigma_muon, h_sigma_fake, h_sigma_signal['higgsino_300_1000'], i, 'sigma', canvas, rebin=5)

    for dataset in h_disc_signal:
        for i in [4, 5, 6]:
            wp = getWP(h_disc_ele, h_sigma_ele, h_disc_muon, h_sigma_muon, h_disc_fake, h_sigma_fake, h_disc_signal[dataset], h_sigma_signal[dataset], i)
            print dataset, '--', wp

    iClone = -1

    print '\nComparing disc < 0.3 to fiducial map method:\n'
    printChanges('Electrons nLayers=4',  h_sigma_ele, h_disc_ele, 0.3, 4, iClone)
    printChanges('Electrons nLayers=5',  h_sigma_ele, h_disc_ele, 0.3, 5, iClone)
    printChanges('Electrons nLayers>=6', h_sigma_ele, h_disc_ele, 0.3, 6, iClone)

    printChanges('Muons nLayers=4',  h_sigma_muon, h_disc_muon, 0.3, 4, iClone)
    printChanges('Muons nLayers=5',  h_sigma_muon, h_disc_muon, 0.3, 5, iClone)
    printChanges('Muons nLayers>=6', h_sigma_muon, h_disc_muon, 0.3, 6, iClone)

    printChanges('Fakes nLayers=4',  h_sigma_fake, h_disc_fake, 0.3, 4, iClone)
    printChanges('Fakes nLayers=5',  h_sigma_fake, h_disc_fake, 0.3, 5, iClone)
    printChanges('Fakes nLayers>=6', h_sigma_fake, h_disc_fake, 0.3, 6, iClone)

    extra_samples = {
        10    : ['0p' + str(i) for i in range(2, 10)] + [str(i) for i in range(0, 10)],
        100   : [str(i*10) for i in range(2, 10)],
        1000  : [str(i*100) for i in range(2, 10)],
        10000 : [str(i*1000) for i in range(2, 10)],
    }

    for i in [4, 5, 6]:
        print 'NLAYERS: ', i
        for mass in range(100, 1000, 100):
            for lifetime in [10, 100, 1000, 10000]:
                datasetName = 'higgsino_%d_%d' % (mass, lifetime)
                change_string = printChanges('Higgsino_%dGeV_%dcm_94X' % (mass, lifetime), 
                                             h_sigma_signal[datasetName], 
                                             h_disc_signal[datasetName], 
                                             0.3, 
                                             i,
                                             iClone)
                for extra_lifetime in extra_samples[lifetime]:
                    print change_string.replace('Higgsino_%dGeV_%dcm_94X' % (mass, lifetime), 'Higgsino_%dGeV_%scm_94X' % (mass, extra_lifetime))

#######################################

datasets = {
    'electrons' : '/store/user/bfrancis/images_v5/SingleEle_2017F/hist_*.root',
    'muons'     : '/store/user/bfrancis/images_v5/SingleMu_2017F/hist_*.root',
    'fake'      : '/store/user/bfrancis/images_v5/ZtoMuMu_2017F/hist_*.root',
}

datasets.update(
    { 'higgsino_%d_%d' % (mass, lifetime) : '/store/user/bfrancis/images_v5/higgsino_%d_%d/hist_*.root' % (mass, lifetime) for mass in range(100, 1000, 100) for lifetime in [10, 100, 1000, 10000] }
)

#for dataset in datasets:
#   processDataset(dataset, datasets[dataset])

analyze(datasets, 'save_noReco')
