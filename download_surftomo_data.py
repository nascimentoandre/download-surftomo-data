from obspy import read, read_inventory
from obspy.clients.fdsn import Client
from obspy.geodetics.base import kilometers2degrees
from fetchtool.BaseBuilder import Range, AreaRange
from fetchtool.Builders import FDSNBuilder
from fetchtool.Downloader import Downloader, FDSNFetcher
from fetchtool.Savers import SacSaver
import os
import argparse
from time import time
from shutil import copy, rmtree

def request_data(folder, t0, t1, preset, offset, ev_area_str, sta_area_str, min_mag, max_depth, hor_comp, fdsn_servers, auth):
    # Defining areas for events and stations
    if ev_area_str == None:
        ev_area = AreaRange.WORLD()
    else:
        ev_area_str = ev_area_str.strip("()")
        xmin, xmax = float(ev_area_str.split("/")[0]), float(ev_area_str.split("/")[1])
        ymin, ymax = float(ev_area_str.split("/")[2]), float(ev_area_str.split("/")[3])
        ev_area = AreaRange(xmin, xmax, ymin, ymax)

    if sta_area_str == None:
        sta_area = AreaRange.BRAZIL()
    else:
        sta_area_str = sta_area_str.strip("()")
        xmin, xmax = float(sta_area_str.split("/")[0]), float(sta_area_str.split("/")[1])
        ymin, ymax = float(sta_area_str.split("/")[2]), float(sta_area_str.split("/")[3])
        sta_area = AreaRange(xmin, xmax, ymin, ymax)

    if not os.path.isdir(folder):
        os.mkdir(folder)
    os.chdir(folder)

    for server in fdsn_servers.split(","):
        # Building the request
        rb = FDSNBuilder("usgs", server)

        rq = rb.eventBased(t0, t1, 20.0, ["H"], Range(preset*-1, offset), "Ot", ev_area,
                           Range(min_mag, 10), Range(0, max_depth), stationRestrictionArea=sta_area)

        if not hor_comp:
            rq = rb.filter_channels(rq, "Z")

        print("Downloading data from %s."%server)
        if server.upper() == "USP":
            if auth:
                cred = open("../credentials", "r")
                user = cred.readline().strip()
                password = cred.readline().strip()
                link = "http://seisrequest.iag.usp.br;%s;%s"%(user, password)
            else:
                link = "http://seisrequest.iag.usp.br"
        else:
            link = server

        ft = FDSNFetcher(link)
        sv = SacSaver()

        dl = Downloader('./%s'%server, replacetree=True, show_resume=True, fetcher=ft, saverlist=[sv])
        dl.work(rq)

def clean_data(fdsn_servers):
    print("Reorganizing data\n")
    events = []

    for server in fdsn_servers.split(","):
        ev_tmp = os.listdir(server)
        for ev in ev_tmp:
            n_files = len(os.listdir("./%s/%s"%(server, ev)))
            if not ev in events and n_files > 0:
                events.append(ev)

    for folder in events:
        if not os.path.isdir(folder):
            os.mkdir("%s"%folder)
            os.mkdir("%s/raw"%folder)
            os.mkdir("%s/resp"%folder)

    allowed_channels = ["HHZ", "BHZ", "LHZ", "HHN", "BHN", "LHN", "HHE", "BHE", "LHE",
                        "HH1", "BH1", "LH1", "HH2", "BH2", "LH2"]

    # copying data from multiple servers to the corresponding event folder
    for event in events:
        for server in fdsn_servers.split(","):
            if os.path.isdir("./%s/%s"%(server, event)):
                client = Client(server)
                files = os.listdir("./%s/%s"%(server, event))
                for file in files:
                    st = read("./%s/%s/%s"%(server, event, file))
                    dist = kilometers2degrees(st[0].stats.sac["dist"])
                    if not os.path.isfile("./%s/raw/%s"%(event, file)) and file.split(".")[-2] in allowed_channels and dist >= 15.0:
                        copy("%s/%s/%s"%(server, event, file), "%s/raw"%(event))
                        net = file.split(".")[0]
                        sta = file.split(".")[1]
                        cha = file.split(".")[-2]
                        # downloading response
                        try:
                            inv = client.get_stations(network=net, station=sta, channel=cha, level="response", filename="./%s/resp/STXML.%s.%s.%s"%(event, net, sta, cha))
                            print("Downloaded response for %s.%s"%(net, sta))
                        except Exception as e:
                            # deveria arrumar essa parte pra salvar em um arquivo caso tenha problema
                            # mas vou deixar como está por enquanto
                            print("%s %s %s"%(event, net, sta))
                            print(e)

    # deleting data from previous folders
    for server in fdsn_servers.split(","):
        rmtree(server)

def process_data(pre_filt):
    print("Processing data\n")
    events = os.listdir("./")
    pre_filt = (float(pre_filt.split(",")[0]), float(pre_filt.split(",")[1]),
                     float(pre_filt.split(",")[2]), float(pre_filt.split(",")[3]))
    for event in events:
        print(event)
        os.chdir(event)
        os.mkdir("proc")
        files = os.listdir("raw")
        for file in files:
            st = read("raw/%s"%file)
            net = file.split(".")[0]
            sta = file.split(".")[1]
            cha = file.split(".")[-2]
            # default parameters:
            # Trace.remove_response(inventory=None, output='VEL', water_level=60, pre_filt=None,
            # zero_mean=True, taper=True, taper_fraction=0.05, plot=False, fig=None, **kwargs
            inv = read_inventory("./resp/STXML.%s.%s.%s"%(net, sta, cha))
            try:
                st.remove_response(inventory=inv, output="DISP", pre_filt=pre_filt)
                st.detrend('linear')
                st.interpolate(10)
                st.write("proc/%s"%file)
                print("Processed %s.%s"%(net, sta))
            except:
                print("Error while processing: %s %s %s"%(event, net, sta))
        os.chdir("./..")

if __name__ == "__main__":
    t1 = time()

    parser = argparse.ArgumentParser(description="Download seismic data from IRIS and USP, intended for surface wave tomography.")
    parser.add_argument("--folder", type=str, metavar="", required=True, help="Path where the data will be saved.")
    parser.add_argument("--t0", type=str, metavar="", required=True, help="Initial date string. Ex: 2010-10-01")
    parser.add_argument("--t1", type=str, metavar="", required=True, help="Final date string. Ex: 2020-12-31")
    parser.add_argument("--preset", type=int, metavar="", default=200, help="Time in seconds prior to origin time.")
    parser.add_argument("--offset", type=int, metavar="", default=4000, help="Time in seconds after origin time.")
    parser.add_argument("--sta_area", type=str, metavar="", help="xmin/xmax/ymin/ymax. If not provided, defaults to Brazil.")
    parser.add_argument("--ev_area", type=str, metavar="", help="(xmin/xmax/ymin/ymax). If not provided, defaults to the entire world.")
    parser.add_argument("--min_mag", type=float, metavar="", default=5.5, help="Minimum magnitude. Default is 5.5")
    parser.add_argument("--min_epi", type=float, metavar="", default=15.0, help="Minimum source-receiver distance in degrees. Default is 15 degrees.")
    parser.add_argument("--max_depth", type=float, metavar="", default=100.0, help="Maximum hypocentral depth. Default is 100 km.")
    parser.add_argument("--pre_filt", type=str, metavar="", default="0.001,0.004,2,3", help="Pre filter used for removing instrument response. Example: '0.001,0.004,2,3'")
    parser.add_argument("--auth", type=bool, metavar="", default=False, help="Whether to authenticate in USP or not. If True, a file with the credentials must be in the folder.")
    parser.add_argument("--hor_comp", type=bool, metavar="", default=False, help="Whether to keep horizontal components in the query or not")
    parser.add_argument("--fdsn_servers", type=str, metavar="", default="IRIS,USP", help="List of FDSN servers from which data will be retrieved.")

    args = parser.parse_args()

    request_data(args.folder, args.t0, args.t1, args.preset, args.offset, args.ev_area,
                 args.sta_area, args.min_mag, args.max_depth, args.hor_comp, args.fdsn_servers,
                 args.auth)

    clean_data(args.fdsn_servers)
    process_data(args.pre_filt)

    t2 = time()

    dt = t2 - t1
    hours = dt // 3600
    minutes = (dt%3600) // 60
    seconds = dt - (hours*3600) - (minutes*60)
    print("Time elapsed: %.f hours, %.f minutes and %.f seconds" %(hours, minutes, seconds))
