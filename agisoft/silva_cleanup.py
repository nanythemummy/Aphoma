#!/usr/bin/env python
################################################################################
# Script : silva_cleanup.py
# Author : George Chlipala
# Created: Feb 26, 2018
# -- Description ----------------------------------------
# This script cleanup taxonomy files from Silva
# -- Requirements ---------------------------------------
# Python 2.7
# Python modules argparse, re, traceback
################################################################################

__author__ = "George Chlipala"
__license__ = "GPL"
__maintainer__ = "George Chlipala"
__email__ = "gchlip2@uic.edu"

import os
import sys
import argparse
import re
import traceback
from string import strip

# Regex tests for "fake" names
RE_TESTS = [ re.compile('^(D_[0-9]__)uncultured (.+ sp\.)$'), re.compile('^(D_[0-9]__)[a-zA-Z0-9]+ sp\.'), 
    re.compile('^(D_[0-9]__)uncultured'), re.compile('^(D_[0-9]__).*metagenome'), 
    re.compile('^(D_[0-9]__)unidentified'), 
    re.compile('^(D_[0-9]__)bacterium'), re.compile('^(D_6__[a-zA-Z0-9]+ [a-zA-Z0-9]+) .+$') ]

# Regex to determine is a name has the proper silva format
silva_name = re.compile('^D_[0-9]__')

## regex to strip genus from the D_6 name
silva_genus_6 = re.compile('^D_6__([a-zA-Z0-9]+) [a-zA-Z0-9]+')
silva_genus_5 = re.compile('^D_5__([a-zA-Z0-9]+) [a-zA-Z0-9]+')

# "Real" names in Silva all start with a capital letter
suprious_name = re.compile('^(D_6__)[a-z]')

##
# method to clean taxonomy to strip "fake" names
def clean_taxonomy(taxonomy):
    cleaned_taxa = []
    taxa = re.split(' *; *', taxonomy)
    # For each name in the full taxonomic name, clean the name
    for t, taxon in enumerate(taxa):
        if not silva_name.search(taxon):
            # If the name is not in proper "Silva" format, then generate a stub name
            cleaned_taxa.append("D_{}__".format(t))
        else:
            # Clean the name
            cleaned_taxa.append(clean_taxon(taxon))

    return cleaned_taxa

##
# method to clean a particular taxon
def clean_taxon(taxon):
    # Check if the taxon matches on of the tests.  
    # If so return the capture group
    for test in RE_TESTS:
        match = test.search(taxon)
        if match is not None:
            return match.group(1)

    # Check if the name is a "suprious" name, 
    # i.e. all Silva names should start with a capital letter
    match = suprious_name.search(taxon)
    if match is not None:
        sys.stderr.write('Spurious name: ' + taxon + "\n")
        return match.group(1)

    return taxon

##
# Main subroutine
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Clean up Silva taxonomy files")
        parser.add_argument('-i', "--input",  help="Input taxonomy file")
        parser.add_argument('-o', "--output",  help="Output taxonomy file")
        parser.add_argument('-f', '--filter_inconsistent', dest='filter_taxa', default=False, action='store_true',
            help='Filter taxa that are inconsitent (different D_5__ name and genus name at D_6__ level)')
        parser.add_argument('--filter_out', help="File to log references that were filtered")
        opts = parser.parse_args()
    
        # Setup the input 
        if opts.input is not None:
            input = open(opts.input)
        else:
            input = sys.stdin
    
        # Setup the output
        if opts.output is not None:
            of = open(opts.output,'w')
        else: 
            of = sys.stdout
    
        # If the list of removed names should be saved, create that output file
        if opts.filter_out is not None:
            filter_out = open(opts.filter_out, 'w')
    
        # Process each line of the Silva taxonomy file
        for line in input:
            line = line.strip()
            if line:
                # Get the sequence ID and associated taxonomy
                identifier, taxonomy = map(strip, line.split('\t'))
                # Get the cleaned taxonomy for the sequence
                taxa = clean_taxonomy(taxonomy)
                # If the filter was set, then filter if the genus in the D_6__ name matches the D_5__ name
                if opts.filter_taxa:
                    match = silva_genus_6.search(taxa[6])
                    if match is not None:
                        # Looks like a valid D_6__ name, get the genus in that name
                        genus_6 = match.group(1)
                        # Remove the D_5__ prefix from the name
                        # And if name has any additional text, strip remaning components
                        genus = taxa[5][5:].split(" ")[0]
                        # If there is a "-" in the genus. split and see if the taxon is in the list
                        # If the D_6__ name is not in the list, skip this reference
                        if genus_6 not in genus.strip().split('-'):
                            if opts.filter_out is not None:
                                filter_out.write("\t".join([identifier, ";".join(taxa)]) + "\n")
                            continue
                of.write("\t".join([identifier, ";".join(taxa)]) + "\n")
    
        # Close the output, if necessary
        if opts.output is not None:
            of.close()
    
        # Close the input, if necessary
        if opts.input is not None:
            input.close()

        # Close the filter_out, if necessary
        if opts.filter_out is not None:
            filter_out.close()

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
