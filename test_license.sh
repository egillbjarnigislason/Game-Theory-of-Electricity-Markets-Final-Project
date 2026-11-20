#BSUB -J lic_test
#BSUB -q hpc
#BSUB -n 1
#BSUB -R "rusage[mem=1GB]"
#BSUB -W 00:05
#BSUB -o job_out/lic_%J.out
#BSUB -e job_out/lic_%J.err
cd "$LS_SUBCWD"
module load python3/3.11.13
module load gurobipy/gurobi-13.0.0-python-3.11.13
source .venv/bin/activate
echo "host: $(hostname)"
echo "GRB_LICENSE_FILE=$GRB_LICENSE_FILE"
echo "PYTHONPATH=$PYTHONPATH"
python - <<'PY'
import gurobipy, socket
print("gurobipy from", gurobipy.__file__, gurobipy.gurobi.version())
try:
    socket.create_connection(("license1.cc.dtu.dk", 4195), 5).close()
    print("token server reachable")
except Exception as e:
    print("token server NOT reachable:", e)
m = gurobipy.Model(); x = m.addVars(3000, ub=1.0)
m.setObjective(x.sum(), gurobipy.GRB.MAXIMIZE); m.optimize()
print("FULL LICENSE OK")
PY
