"""2024+ quarter-by-quarter ATP/WTA offline feature-ablation study.

No production writes or provider calls. Tournament start is not match time:
pre_match.build_features enforces 21 days of history embargo. The experiment
fits on calendar-time earlier data, calibrates on a disjoint 60-day interval,
and measures each model on identical complete-case fixtures.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

from .pre_match import build_features
from .evaluate import eligible, train, fit_platt, sigmoid, logit

ARMS = {
    "BASE": ("elo_diff", "rank_diff", "age_interval_diff"),
    "SURFACE_ELO": ("elo_diff", "rank_diff", "age_interval_diff", "surface_elo_shrunk_diff"),
    "SURFACE_FORM": ("elo_diff", "rank_diff", "age_interval_diff", "surface_elo_shrunk_diff",
                     "shrunk_surface_form_diff"),
    "SURFACE_POINT": ("elo_diff", "rank_diff", "age_interval_diff", "surface_elo_shrunk_diff",
                      "shrunk_surface_form_diff", "shrunk_surface_serve_diff",
                      "shrunk_surface_return_diff"),
    "OPP_ADJUSTED": ("elo_diff", "rank_diff", "age_interval_diff", "surface_elo_shrunk_diff",
                      "shrunk_surface_form_diff", "shrunk_surface_serve_diff",
                      "shrunk_surface_return_diff", "adjusted_serve20_diff"),
}
QUARTERS = ("2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01",
            "2026-01-01", "2026-04-01", "2026-07-01")


def metrics(preds):
    n=len(preds)
    if not n:
        return {"n":0,"accuracy":None,"brier":None,"log_loss":None,
                "threshold80":{"n":0,"coverage":None,"accuracy":None}}
    import math
    correct = sum(int((p >= .5) == bool(y)) for p,y in preds)
    bs = sum((p-y)**2 for p,y in preds)/n
    ll = sum(-y*math.log(max(1e-12,p))-(1-y)*math.log(max(1e-12,1-p)) for p,y in preds)/n
    chosen = [(p,y) for p,y in preds if max(p,1-p)>=.8]
    return {"n":n,"accuracy":round(correct/n,6),"brier":round(bs,6),
            "log_loss":round(ll,6),
            "threshold80":{"n":len(chosen),"coverage":round(len(chosen)/n,6),
                           "accuracy":round(sum(int((p>=.5)==bool(y)) for p,y in chosen)/len(chosen),6) if chosen else None}}


def study(rows):
    rows=sorted(list(rows),key=lambda r:(r["date"],r["match_id"]))
    if any(r["date"] < "2024-01-01" for r in rows):
        raise ValueError("Supervised input rows must be 2024+")
    if len({r["match_id"] for r in rows})!=len(rows):
        raise ValueError("Duplicate match identity")
    report={"status":"COMPLETED_RESEARCH_ONLY","production_mutated":False,
            "provider_requests":0,"model_promotion":False,
            "method":"2024+ expanding fit; disjoint prior 60 days calibration; quarter test",
            "candidates":{k:list(v) for k,v in ARMS.items()},
            "year_scope":"2024+ only","embargo_days":21,
            "folds":[]}
    for start in QUARTERS:
        startdate=date.fromisoformat(start)
        end_month = startdate.month + 3
        endyear = startdate.year + (end_month>12)
        if end_month>12: end_month-=12
        end=date(endyear,end_month,1).isoformat()
        cal_start=(startdate-timedelta(days=60)).isoformat()
        fitting=[r for r in rows if r["date"] < cal_start]
        calibration=[r for r in rows if cal_start <= r["date"] < start]
        testing=[r for r in rows if start <= r["date"] < end]
        fold={"test_start":start,"test_end_exclusive":end,"calibration_start":cal_start,
              "n_fit_available":len(fitting),"n_calibration_available":len(calibration),
              "n_test_available":len(testing),"models":{}}
        if len(fitting)<300 or len(calibration)<80 or len(testing)<80:
            fold["status"]="INSUFFICIENT_DATA"
            report["folds"].append(fold)
            continue
        heldout={}
        for name,keys in ARMS.items():
            ft=[r for r in fitting if eligible(r,keys)]
            ca=[r for r in calibration if eligible(r,keys)]
            te=[r for r in testing if eligible(r,keys)]
            if min(len(ft),len(ca),len(te)) < 80:
                fold["models"][name]={"status":"INSUFFICIENT_COMPLETE_CASE","n_fit":len(ft),
                                       "n_cal":len(ca),"n_test":len(te)}
                continue
            estimator=train(ft, keys, iterations=500)
            cal_preds=[(estimator.predict(r),r["y"]) for r in ca]
            slope, offset=fit_platt(cal_preds)
            outputs={}
            for r in te:
                raw=estimator.predict(r)
                outputs[r["match_id"]]={"raw":raw,
                                        "calibrated":sigmoid(slope*logit(raw)+offset),
                                        "y":int(r["y"]), "surface":r["surface"]}
            heldout[name]=outputs
            fold["models"][name]={"status":"EVALUATED","n_fit":len(ft),
                                   "n_cal":len(ca),"n_test":len(te),
                                   "platt_slope":slope,"platt_offset":offset,
                                   "coverage":round(len(te)/len(testing),6)}
        common=set.intersection(*(set(x) for x in heldout.values())) if len(heldout)==len(ARMS) else set()
        fold["common_cohort_n"]=len(common)
        if common:
            for name,points in heldout.items():
                ordered=[points[mid] for mid in sorted(common)]
                outcome=fold["models"][name]
                outcome["raw"]=metrics([(x["raw"],x["y"]) for x in ordered])
                outcome["calibrated"]=metrics([(x["calibrated"],x["y"]) for x in ordered])
                outcome["by_surface"]={s:metrics([(x["calibrated"],x["y"]) for x in ordered if x["surface"]==s])
                                       for s in ("hard","clay","grass")}
                # Evaluate each candidate on exactly the baseline's >=80% decisions
                # to distinguish predictive gain from smaller/harder selection cohorts.
                base=heldout["BASE"]
                baseline80=[mid for mid in sorted(common) if max(base[mid]["calibrated"],
                                                 1-base[mid]["calibrated"]) >= .8]
                outcome["on_base80_cohort"]=metrics([(points[mid]["calibrated"],points[mid]["y"])
                                                    for mid in baseline80])
        fold["status"]="EVALUATED" if common else "NO_COMMON_COMPLETE_CASE"
        report["folds"].append(fold)
    report["evaluated_folds"]=sum(x["status"]=="EVALUATED" for x in report["folds"])
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tour",choices=["ATP","WTA"],required=True)
    ap.add_argument("--input",type=Path,action="append",required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    paths=sorted(set(args.input))
    sources=[]
    for path in paths:
        data=path.read_bytes()
        sources.append({"path":str(path),"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)})
    def source_rows():
        for path in paths:
            with path.open("r",encoding="utf-8-sig",newline="") as h:
                yield from csv.DictReader(h)
    features, rejected=build_features(source_rows(),args.tour)
    result=study(features)
    result["source"]={"tour":args.tour,"files":sources,
                       "accepted":len(features),"quarantined":len(rejected)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False),encoding="utf-8")
    print(json.dumps({"status":result["status"],"folds":result["evaluated_folds"],
                      "accepted":len(features),"quarantined":len(rejected),
                      "result":str(args.output)},sort_keys=True))

if __name__=="__main__":
    main()
