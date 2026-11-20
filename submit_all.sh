#!/bin/bash
# Submits one LSF job per case. Run on the login node from the repo folder:  bash submit_all.sh
#
# The case file and soft limit are written INTO a copy of run_case.sh that is piped to bsub.
# (Environment variables set in front of bsub, e.g. CASE=... bsub < run_case.sh, did NOT reach the job on DTU's cluster.)

mkdir -p job_out runs      # LSF will NOT create the output folder; the job fails silently without it

#       case file                                   soft limit (s)   hard limit (hh:mm)
submit() {
    local case_file="$1" soft="$2" wall="$3"
    local name="poa_$(basename "$case_file" .m | sed 's/pglib_opf_case//; s/_.*//')"
    sed -e "s|^CASE=.*|CASE=\"${case_file}\"|" \
        -e "s|^SOFT_LIMIT=.*|SOFT_LIMIT=${soft}|" run_case.sh \
      | bsub -J "$name" -W "$wall"
}

submit "ieee data/pglib_opf_case14_ieee.m"       7000 02:00
submit "ieee data/pglib_opf_case24_ieee_rts.m"   7000 02:00   # crashes until the player-index bug is fixed
submit "ieee data/pglib_opf_case30_ieee.m"       7000 02:00
submit "ieee data/pglib_opf_case57_ieee.m"       7000 02:00   # crashes until the player-index bug is fixed
submit "ieee data/pglib_opf_case73_ieee_rts.m"   7000 02:00   # crashes until the player-index bug is fixed
submit "ieee data/pglib_opf_case118_ieee.m"      7000 02:00   # crashes until the player-index bug is fixed
submit "ieee data/pglib_opf_case162_ieee_dtc.m"  7000 02:00   # main loop only; the CCE step will not finish
submit "ieee data/pglib_opf_case300_ieee.m"      7000 02:00   # crashes until the player-index bug is fixed
