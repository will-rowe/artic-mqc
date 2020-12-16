#!/usr/bin/env python

""" MultiQC example plugin module """

from __future__ import print_function
from collections import OrderedDict
import logging

from multiqc import config
from multiqc.plots import linegraph
from multiqc.modules.base_module import BaseMultiqcModule

# Initialise the main MultiQC logger
log = logging.getLogger('multiqc')

# Minimum read count for amplicon coverage - any below will be flagged
Amplicon_Dropout_Val = 50


class MultiqcModule(BaseMultiqcModule):

    def __init__(self):

        # Halt execution if we've disabled the plugin
        if config.kwargs.get('disable_plugin', True):
            return None

        # Initialise the parent module Class object
        super(MultiqcModule, self).__init__(
            name='ARTIC',
            target="artic-mqc",
            anchor='artic-mqc',
            href='https://github.com/will-rowe/artic-mqc',
            info=" is a plugin for the <a href=\"https://github.com/artic-network/fieldbioinformatics\">ARTIC Network pipeline.</a>"
        )

        # Find the align_trim reports
        self.artic_align_trim_data = dict()
        for f in self.find_log_files('artic_mqc/aligntrim_reports', filehandles=True):
            self.artic_align_trim_data[f['s_name']] = dict()
            _ = f['f'].readline()

            # Bin reads by amplicon (keeping entire lines for now but might just use a counter)
            for l in f['f']:
                fields = l.split('\t')
                if fields[3] not in self.artic_align_trim_data[f['s_name']]:
                    self.artic_align_trim_data[f['s_name']][fields[3]] = []
                self.artic_align_trim_data[f['s_name']][fields[3]].append(l)

        # Find the vcf_checker reports
        self.artic_vcf_checker_data = dict()
        for f in self.find_log_files('artic_mqc/vcfcheck_reports'):
            self.artic_vcf_checker_data[f['s_name']] = dict()
            for l in f['f'].splitlines():
                key, value = l.split(None, 1)
                self.artic_vcf_checker_data[f['s_name']][key] = value

        # Filter out samples matching ignored sample names
        self.artic_align_trim_data = self.ignore_samples(
            self.artic_align_trim_data)
        self.artic_vcf_checker_data = self.ignore_samples(
            self.artic_vcf_checker_data)

        # Nothing found - raise a UserWarning to tell MultiQC
        if len(self.artic_align_trim_data) == 0:
            log.debug("Could not find any reports in {}".format(
                config.analysis_dir))
            raise UserWarning

        # Log files
        log.info("Found {} align_trim reports".format(
            len(self.artic_align_trim_data)))
        log.info("Found {} vcf_checker reports".format(
            len(self.artic_vcf_checker_data)))

        # Process data from files
        # 1. check amplicon coverage for plotting and dropouts
        self.amplicon_counts = dict()
        self.qc_stats = dict()
        for sampleName, sampleData in self.artic_align_trim_data.items():
            self.amplicon_counts[sampleName] = {}
            self.qc_stats[sampleName] = {
                'amplicon_dropouts': 0,
                'overlap_fails': 0
            }
            for ampliconName, reads in sampleData.items():
                self.amplicon_counts[sampleName][ampliconName] = len(reads)
                if self.amplicon_counts[sampleName][ampliconName] < Amplicon_Dropout_Val:
                    self.qc_stats[sampleName]['amplicon_dropouts'] += 1

        # Write parsed report data to a file
        self.write_data_file(self.artic_align_trim_data, 'artic')

        # Add a number to General Statistics table
        headers = OrderedDict()
        headers['amplicon_dropouts'] = {
            'title': '# low cov. amplicons',
            'description': 'The number of amplicons for this sample with coverage <{}' .format(Amplicon_Dropout_Val),
            'min': 0,
            'scale': 'RdYlGn-rev',
            'format': '{:,.0f}'
        }
        headers['overlap_fails'] = {
            'title': '# overlap fails',
            'description': 'The number of variants detected only once in scheme overlap regions',
            'min': 0,
            'scale': 'RdYlGn-rev',
            'format': '{:,.0f}'
        }
        self.general_stats_addcols(self.qc_stats, headers)

        # Add in the amplicon coverage plot
        # see: https://multiqc.info/docs/#step-6-plot-some-data
        pconfig = {
            'id': 'amplicon_plot',
            'title': 'Amplicon Coverage',
            'ylab': '# reads',
            'xlab': 'amplicon',
            'categories': True
        }
        amplicon_plot_html = linegraph.plot(self.amplicon_counts, pconfig)
        self.add_section(
            name='Amplicon coverage',
            anchor='artic-amplicon-cov',
            #description='Mean depth of coverage per amplicon.',
            helptext='''
            This plot summarises the number of reads that were assigned to each amplicon.

            We use the `align_trim` report file and group each read by its assigned amplicon.

            Assumptions:
            * the same scheme was used across samples (no check implements in this multiqc report yet)
            * full-length amplicon alignments were required during the artic pipeline run
            ''',
            plot=amplicon_plot_html
        )
