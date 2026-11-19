#!/bin/bash
# LSF job script: runs main.py for ONE case file.
# Submit with:   CASE="ieee data/pglib_opf_case14_ieee.m" bsub < run_case.sh
# (or use submit_all.sh). Directives below are the defaults; command-line bsub options override them.

#BSUB -J poa_case
#BSUB -q hpc
#BSUB -n 4
#BSUB -R "span[hosts=1]"
#BSUB -R "rusage[mem=4GB]"
#BSUB -M 5GB
#BSUB -W 04:00
#BSUB -o job_out/%J.out
#BSUB -e job_out/%J.err

# ---- settings -------------------------------------------------------------
CASE="${CASE:-ieee data/pglib_opf_case14_ieee.m}"
# Soft limit in seconds. main.py only checks it BETWEEN cutting-plane iterations,
# so keep it well below the hard -W limit (4h = 14400 s) to leave room for one long oracle solve.
SOFT_LIMIT="${SOFT_LIMIT:-10800}"
# ---------------------------------------------------------------------------

cd "$LS_SUBCWD" || exit 1        # directory bsub was called from (the repo folder)

module load python3/3.11.13      # modules do not persist between sessions, so load them in the job
module load gurobipy/gurobi-13.0.0-python-3.11.13   # DTU Gurobi 13 + license (also loads gurobi/13.0.0)

if [ ! -d .venv ]; then
    echo "No .venv found in $(pwd). Create it once on the login node (see README_HPC.md)." >&2
    exit 1
fi
source .venv/bin/activate

# Every job gets its own working directory so Gurobi temp/log files never collide,
# and Gurobi is told to use exactly the cores LSF gave us (default would grab all cores on the node).
RUN_DIR="runs/${LSB_JOBID}_$(basename "$CASE" .m)"
mkdir -p "$RUN_DIR"
export NTHREADS="${LSB_DJOB_NUMPROC:-4}"
cat > "$RUN_DIR/gurobi.env" <<ENV
Threads $NTHREADS
ENV

echo "Job $LSB_JOBID on $(hostname), cores=$NTHREADS, case='$CASE', soft limit=${SOFT_LIMIT}s"
date

# Run from RUN_DIR (gurobi.env is read from cwd); main.py and the case file are referenced by absolute path.
REPO="$(pwd)"
cd "$RUN_DIR"
python -u "$REPO/main.py" "$REPO/$CASE" "$SOFT_LIMIT" > result.txt 2>&1
STATUS=$?
echo "main.py exited with status $STATUS"
date
tail -n 15 result.txt
exit $STATUS
