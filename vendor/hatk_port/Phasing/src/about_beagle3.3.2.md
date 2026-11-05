# BEAGLE v3.3.2 Command-Line Arguments

This document provides a summary of command-line arguments for **BEAGLE v3.3.2**, which is used for haplotype phasing within HATK. While this is an older version of BEAGLE, it is recommended for compatibility with certain HATK modules like the Omnibus Test.

**Important Note**: BEAGLE v3.3.2 does NOT support multithreading (`nthreads` parameter). It always runs on a single thread. For multithreading support, use BEAGLE v4.x + instead.

The official BEAGLE v3.3.2 software can be downloaded from: [https://faculty.washington.edu/browning/beagle/b3.html](https://faculty.washington.edu/browning/beagle/b3.html)

## Quick Start

To run BEAGLE, use the following command structure:

```bash
java -Xmx<Mb>m -jar beagle.jar <arguments>
```

-   `<Mb>`: The amount of memory to allocate in Megabytes (e.g., `-Xmx1000m` for 1GB).
-   `<arguments>`: A space-separated list of `parameter=value` arguments.

---

## Command-Line Arguments

### File Arguments

These arguments are used to specify input and output files.

*   `unphased=<file>`
    *   Specifies a Beagle file with unphased, unrelated genotype data. Multiple `unphased` arguments can be used for different cohorts.

*   `phased=<file>`
    *   Specifies a Beagle file with phased, unrelated data. Can be used multiple times.

*   `trios=<file>`
    *   Specifies a Beagle file with unphased parent-offspring trio data. Can be used multiple times.

*   `pairs=<file>`
    *   Specifies a Beagle file with unphased parent-offspring pair data. Can be used multiple times.

*   `like=<file>`
    *   Specifies a genotype likelihoods file for unphased, unrelated data. Can be used multiple times.

*   `markers=<file>`
    *   **Required if more than one input Beagle file is specified.** This file lists marker identifiers, positions, and alleles.

*   `missing=<char>`
    *   **Required.** The character used to represent a missing allele (e.g., `missing=?` or `missing=0`).

*   `out=<prefix>`
    *   **Required.** The prefix for all output files. Cannot be a directory. Output files will be named `[prefix].[input_filename].[extension]`.

*   `omitprefix=<true/false>`
    *   If `true`, the output prefix is omitted from all filenames except the log file. Default is `false`.

*   `maxlr=<ratio>`
    *   The maximum permitted likelihood ratio for genotype likelihoods. Default is `5000`.

### Other Phasing Arguments

These arguments control the phasing algorithm and other options.

*   `niterations=<number>`
    *   The number of iterations for the phasing algorithm. Must be a positive even integer. Default is `10`.

*   `nsamples=<number>`
    *   Number of haplotype pairs to sample for each individual during each iteration. Default is `4`. Increase for small samples (< 200) for better accuracy, decrease for very large samples (> 4000) to reduce computation time.

*   `gprobs=<true/false>`
    *   If `false`, genotype probability files will not be produced. Recommended to set to `false` if you have sporadic missing data and are not imputing for ungenotyped markers. Default is `true`.

*   `seed=<integer>`
    *   An integer to seed the random number generator. Default is `-99999`.

*   `lowmem=<true/false>`
    *   If `true`, uses a memory-efficient (but slower) implementation. Useful when the number of markers is very large. Default is `false`.

*   `excludecolumns=<file>`
    *   A file containing column identifiers (one per line) to be excluded from the analysis.

*   `excludemarkers=<file>`
    *   A file containing marker identifiers (one per line) to be excluded from the analysis.

*   `verbose=<true/false>`
    *   If `true`, prints detailed running time and model statistics to the log file for each iteration. Default is `false`.

*   `nimputations=<number>`
    *   Creates a specified number of output files with imputed phased data. Default is `0`.

*   `redundant=<true/false>`
    *   If `true`, transmitted haplotypes are printed twice for trios/pairs (for parent and offspring). Default is `false`. 