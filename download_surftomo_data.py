from obspy import read, read_inventory, UTCDateTime
from fetchtool.BaseBuilder import Range, AreaRange
from fetchtool.Builders import FDSNBuilder
from fetchtool.Downloader import Downloader, FDSNFetcher
from fetchtool.Savers import SacSaver
import os
import argparse
from time import time

def request_data(folder, t0, t1, preset, offset, ev_area_str, sta_area_str, min_mag, max_depth, hor_comp, fdsn_servers):
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


    for server in fdsn_servers.split(","):
        # Building the request
        rb = FDSNBuilder("usgs", server)

        rq = rb.eventBased(t0, t1, 20.0, ["H"], Range(preset*-1, offset), "Ot", ev_area,
                           Range(min_mag, 10), Range(0, max_depth), stationRestrictionArea=sta_area)

        if not hor_comp:
            rq = rb.filter_channels(rq, "Z")

        print("Downloading data from %s."%server)
        if server.upper() == "USP":
            server = "http://seisrequest.iag.usp.br"
        ft = FDSNFetcher(server)
        sv = SacSaver()

        dl = Downloader('./%s'%folder, replacetree=False, show_resume=True, fetcher=ft, saverlist=[sv])
        dl.work(rq)



if __name__ == "__main__":
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
    parser.add_argument("--pre_filt", type=str, metavar="", help="Pre filter used for removing instrument response. Example: '0.001, 0.005, 45, 50'")
    parser.add_argument("--auth", type=bool, metavar="", default=False, help="Whether to authenticateor not. If True, a file with the credentials must be in the folder.")
    parser.add_argument("--hor_comp", type=bool, metavar="", default=False, help="Whether to keep horizontal components in the query or not")
    parser.add_argument("--fdsn_servers", type=str, metavar="", default="IRIS,USP", help="List of FDSN servers from which data will be retrieved.")

    args = parser.parse_args()

    request_data(args.folder, args.t0, args.t1, args.preset, args.offset, args.ev_area,
                 args.sta_area, args.min_mag, args.max_depth, args.hor_comp, args.fdsn_servers)
