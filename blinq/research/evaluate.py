"""Offline expanding-window model and probability calibration comparison.

Model-fit years < calibration year < test year; never writes production output.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Iterable

ELO = ("elo_diff",)
ENHANCED = ("elo_diff", "rank_diff", "age_interval_diff")
POINT = ("elo_diff", "rank_diff", "age_interval_diff", "form20_diff",
         "serve20_diff", "return20_diff", "adjusted_serve20_diff")
POINT_BP = POINT + ("first_serve_won20_diff", "second_serve_won20_diff", "bp_saved20_diff", "bp_converted20_diff")


def eligible(row: dict, keys: tuple[str,...]) -> bool:
    try:
        return all(row.get(k) is not None and math.isfinite(float(row[k])) for k in keys)
    except (ValueError, TypeError):
        return False


def sigmoid(x: float) -> float:
    z = max(-32.0, min(32.0, x))
    return 1.0 / (1.0 + math.exp(-z))


def logit(p: float) -> float:
    p = min(0.999999, max(0.000001, p))
    return math.log(p/(1-p))


@dataclass(frozen=True)
class Logistic:
    keys: tuple[str,...]
    center: tuple[float,...]
    scale: tuple[float,...]
    coef: tuple[float,...]

    def predict(self, row: dict) -> float:
        if not eligible(row, self.keys):
            raise ValueError("Missing feature: abstain, do not impute future data")
        x = [1.0] + [(float(row[k])-m)/s for k,m,s in zip(self.keys,self.center,self.scale)]
        return sigmoid(sum(a*b for a,b in zip(x,self.coef)))


def train(rows: list[dict], keys: tuple[str,...], iterations: int = 650, penalty: float = 0.012) -> Logistic:
    clean = [r for r in rows if eligible(r,keys) and r.get("y") in (0,1)]
    if len(clean) < 40:
        raise ValueError("Too few verified complete rows for regression")
    center = tuple(sum(float(r[k]) for r in clean)/len(clean) for k in keys)
    scale = tuple(max(1e-7, math.sqrt(sum((float(r[k])-m)**2 for r in clean)/len(clean))) for k,m in zip(keys,center))
    X = [(1.0,)+tuple((float(r[k])-m)/s for k,m,s in zip(keys,center,scale)) for r in clean]
    y = [int(r["y"]) for r in clean]
    w = [0.0] * (len(keys)+1)
    n = len(clean)
    for i in range(iterations):
        g = [0.0] * len(w)
        for x, target in zip(X,y):
            err = sigmoid(sum(a*b for a,b in zip(x,w))) - target
            for j,val in enumerate(x):
                g[j] += err*val
        lr = 0.30 / (1.0 + i/350.0)
        for j in range(len(w)):
            w[j] -= lr*(g[j]/n + (penalty*w[j] if j else 0.0))
    return Logistic(keys,center,scale,tuple(w))


def fit_platt(predictions: list[tuple[float,int]]) -> tuple[float,float]:
    """Monotonic Platt scaler (slope>=0) fit only on a preceding season."""
    if len(predictions) < 25:
        raise ValueError("Too few calibration observations")
    a,b = 1.0,0.0
    xx = [max(-5.0,min(5.0,logit(p))) for p,y in predictions]
    yy = [y for p,y in predictions]
    for i in range(600):
        er = [sigmoid(a*x+b)-y for x,y in zip(xx,yy)]
        ga = sum(e*x for e,x in zip(er,xx))/len(xx)
        gb = sum(er)/len(xx)
        lr = 0.14/(1+i/250)
        a = max(0.0, a-lr*ga)
        b -= lr*gb
    return round(a,9),round(b,9)


def metrics(predictions: list[tuple[float,int]]) -> dict:
    if not predictions:
        return {"n":0,"accuracy":None,"brier":None,"log_loss":None}
    n = len(predictions)
    brier = sum((p-y)**2 for p,y in predictions)/n
    ll = sum(-(y*math.log(max(1e-12,p)) + (1-y)*math.log(max(1e-12,1-p))) for p,y in predictions)/n
    accuracy = sum((int(p>0.5)==y) for p,y in predictions)/n
    return {"n":n,"accuracy":round(accuracy,6),"brier":round(brier,6),"log_loss":round(ll,6)}


def walk_forward(rows: Iterable[dict], *, min_train: int = 100, min_calibration: int = 30,
                 min_test: int = 20) -> dict:
    rows = sorted(list(rows), key=lambda r:(r["date"],r["match_id"]))
    years = sorted({r["date"][:4] for r in rows})
    candidates = (("ELO",ELO),("ENHANCED",ENHANCED),("POINT",POINT),("POINT_BP",POINT_BP))
    report = {"method":"expanding_train_prior_to_calibration_prior_to_test",
              "production_enabled":False,"calibration_policy":"prior_year_only",
              "candidate_columns":{name:list(keys) for name,keys in candidates}, "folds":[]}
    for test_year in years[2:]:
        validation_year = str(int(test_year)-1)
        training = [r for r in rows if r["date"][:4] < validation_year]
        calibration = [r for r in rows if r["date"][:4] == validation_year]
        testing = [r for r in rows if r["date"][:4] == test_year]
        if len(training) < min_train or len(calibration) < min_calibration or len(testing) < min_test:
            continue
        fold = {"test_year":test_year,"train_before_year":validation_year,
                "calibration_year":validation_year,"test_total":len(testing),"models":{}}
        for name,keys in candidates:
            fitting = [r for r in training if eligible(r,keys)]
            cal = [r for r in calibration if eligible(r,keys)]
            test = [r for r in testing if eligible(r,keys)]
            if len(fitting)<min_train or len(cal)<min_calibration or len(test)<min_test:
                fold["models"][name] = {"status":"INSUFFICIENT_HISTORY", "n_train":len(fitting),
                                        "n_calibration":len(cal),"n_test":len(test)}
                continue
            model = train(fitting,keys)
            preds_cal = [(model.predict(r),int(r["y"])) for r in cal]
            preds_test = [(model.predict(r),int(r["y"])) for r in test]
            result = {"status":"EVALUATED","n_train":len(fitting),"n_calibration":len(cal),
                      "coverage":round(len(test)/len(testing),6),"raw":metrics(preds_test)}
            a,b = fit_platt(preds_cal)
            preds_platt = [(sigmoid(a*logit(p)+b),y) for p,y in preds_test]
            result["platt"] = metrics(preds_platt)
            result["platt_parameters"] = {"slope":a,"offset":b}
            fold["models"][name] = result
        # Complete-case coverage is reported; models have different populations.
        fold["point_complete_case_test_n"] = sum(eligible(r,POINT) for r in testing)
        report["folds"].append(fold)
    report["evaluated_years"] = len(report["folds"])
    return report
