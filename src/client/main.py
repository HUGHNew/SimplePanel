#!/usr/bin/env python3
from plugins import SystemStatsCollector

def get_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL of the server")
    return parser.parse_args()
def main():
    args = get_args()
    collector = SystemStatsCollector(args.url)
    collector.send_stats()

if __name__ == "__main__":
    main()