"""One-off importer from the 2019 spreadsheet era. Nothing imports this module."""
import csv


def import_spreadsheet(path):
    with open(path) as f:
        return list(csv.DictReader(f))
