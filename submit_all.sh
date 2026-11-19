#!/bin/bash
# Submits one LSF job per case. Run on the login node from the repo folder:  bash submit_all.sh
# Edit the CASES list to choose what to run. Per-case resources override the defaults in run_case.sh.

mkdir -p job_out runs      # LSF will NOT create the output folder; the job fails silently without it

#        case file                                  cores  mem   hard-limit  soft-limit(s)
submit() {
    local case_file="$1" cores="$2" mem="$3" wall="$4" soft="$5"
    local name="poa_$(basename "$case_file" .m | sed 's/pglib_opf_case//')"
    CASE="$case_file" SOFT_LIMIT="$soft" bsub -J "$name" -n "$cores" \
        -R "rusage[mem=${mem}]" -M "$((${mem%GB} + 1))GB" -W "$wall" < run_case.sh
}

# Cases that should work with the code as it is now (small number of players):
submit "ieee data/pglib_opf_case14_ieee.m"  4 4GB 04:00 10800
submit "ieee data/pglib_opf_case30_ieee.m"  4 4GB 04:00 10800
# Works for the main loop, but the CCE step will not finish (25^12 joint actions):
# submit "ieee data/pglib_opf_case162_ieee_dtc.m" 8 8GB 12:00 39600

# Cases below crash until the player-index bug is fixed (see notes) -- uncomment afterwards:
# submit "ieee data/pglib_opf_case24_ieee_rts.m"  4 4GB 04:00 10800
# submit "ieee data/pglib_opf_case57_ieee.m"      4 4GB 04:00 10800
# submit "ieee data/pglib_opf_case73_ieee_rts.m"  8 8GB 12:00 39600
# submit "ieee data/pglib_opf_case118_ieee.m"     8 8GB 12:00 39600
# submit "ieee data/pglib_opf_case300_ieee.m"     8 8GB 24:00 82800
