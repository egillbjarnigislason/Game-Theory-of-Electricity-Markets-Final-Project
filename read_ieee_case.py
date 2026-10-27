
from dataclasses import dataclass, field


@dataclass
class Bus:
    bus_i: int
    type: int      # 1 = PQ, 2 = PV, 3 = reference, 4 = isolated
    Pd: float      # real demand [MW]
    Qd: float      # reactive demand [MVAr]
    Gs: float      # shunt conductance [MW at V = 1 p.u.]
    Bs: float      # shunt susceptance [MVAr at V = 1 p.u.]
    area: int
    Vm: float
    Va: float
    baseKV: float
    zone: int
    Vmax: float
    Vmin: float


@dataclass
class Gen:
    bus: int
    Pg: float
    Qg: float
    Qmax: float
    Qmin: float
    Vg: float
    mBase: float
    status: int
    Pmax: float
    Pmin: float
    label: str = ""    # trailing comment in the file, e.g. "NG", "SYNC"


@dataclass
class GenCost:
    model: int         # 1 = piecewise linear, 2 = polynomial
    startup: float
    shutdown: float
    n: int
    params: list       # model 2: [c2, c1, c0] (highest order first)


@dataclass
class Branch:
    fbus: int
    tbus: int
    r: float
    x: float
    b: float
    rateA: float       # [MVA]
    rateB: float
    rateC: float
    ratio: float       # tap ratio, 0 means plain line
    angle: float       # phase shift [deg]
    status: int
    angmin: float      # [deg]
    angmax: float      # [deg]


@dataclass
class Case:
    name: str
    version: str
    baseMVA: float
    bus: list = field(default_factory=list)
    gen: list = field(default_factory=list)
    gencost: list = field(default_factory=list)   # same order as gen
    branch: list = field(default_factory=list)
    areas: list = field(default_factory=list)     # [(area, reference bus), ...]


def read_case(filename):
    tables, scalars, labels = {}, {}, {}
    current = None
    for line in open(filename):
        code, _, comment = line.partition("%")
        code = code.strip()
        if current is not None:
            if code.startswith("]"):
                current = None
            elif code:
                tables[current].append([float(v) for v in code.rstrip(";").split()])
                labels.setdefault(current, []).append(comment.strip())
        elif code.startswith("mpc.") and "=" in code:
            key, value = [s.strip() for s in code.rstrip(";").split("=", 1)]
            key = key[4:]
            if value.startswith("["):
                current = key
                tables[key] = []
            else:
                scalars[key] = value.strip("'")

    case = Case(
        name=filename.replace("\\", "/").split("/")[-1].removesuffix(".m"),
        version=scalars.get("version", ""),
        baseMVA=float(scalars["baseMVA"]),
    )
    ints = {"bus_i", "type", "area", "zone", "bus", "status", "model", "n", "fbus", "tbus"}

    def build(cls, row, **extra):
        names = list(cls.__dataclass_fields__)[: len(row)]
        return cls(**{n: int(v) if n in ints else v for n, v in zip(names, row)}, **extra)

    case.bus = [build(Bus, r) for r in tables["bus"]]
    case.gen = [build(Gen, r, label=l) for r, l in zip(tables["gen"], labels["gen"])]
    case.branch = [build(Branch, r) for r in tables["branch"]]
    case.gencost = [GenCost(int(r[0]), r[1], r[2], int(r[3]), r[4:]) for r in tables["gencost"]]
    case.areas = [(int(r[0]), int(r[1])) for r in tables.get("areas", [])]
    return case


if __name__ == "__main__":
    import sys
    c = read_case(sys.argv[1])
    print(c.name, len(c.bus), "buses", len(c.gen), "gens", len(c.branch), "branches")
