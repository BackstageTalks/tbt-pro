import math
import unittest
from datetime import date
from ..pre_match import build_features
from ..evaluate import eligible, fit_platt, metrics, train, walk_forward, ELO


def match(day, no, w='A', l='B', surface='Hard', stat=True):
    d=date.fromisoformat(day).strftime('%Y%m%d')
    fields={'tourney_date':d, 'tourney_id':'test-'+d, 'match_num':str(no),
       'winner_id':w,'loser_id':l,'winner_name':'P'+w,'loser_name':'P'+l,
       'surface':surface,'score':'6-4 6-4','winner_rank':'50','loser_rank':'120',
       'winner_age':'28','loser_age':'32'}
    if stat:
        fields.update({'w_svpt':'70','w_1stIn':'40','w_1stWon':'30','w_2ndWon':'20',
            'w_bpSaved':'3','w_bpFaced':'5','l_svpt':'65','l_1stIn':'35',
            'l_1stWon':'24','l_2ndWon':'17','l_bpSaved':'2','l_bpFaced':'7'})
    return fields


class FeatureTests(unittest.TestCase):
    def test_no_same_date_or_21_day_leak(self):
        rows=[match('2025-01-01',1),match('2025-01-01',2,w='B',l='A'),
              match('2025-01-15',1),match('2025-01-23',1)]
        out, rejected=build_features(rows,'ATP')
        self.assertFalse(rejected)
        self.assertEqual([x['p1_history_n'] for x in out],[0,0,0,2])
        self.assertIsNone(out[2]['elo_diff'])
        self.assertIsNotNone(out[3]['elo_diff'])
        self.assertEqual(out[0]['y'],1)
        self.assertEqual(out[1]['y'],0)
        self.assertTrue(all(row['feature_asof_before']==row['date'] for row in out))

    def test_opponent_adjustment_uses_old_opp_only(self):
        rows=[match('2025-01-01',1,w='A',l='B'),
              match('2025-01-23',1,w='B',l='C'),
              match('2025-02-15',1,w='A',l='B'),
              match('2025-03-10',1,w='A',l='B')]
        out,_=build_features(rows,'WTA')
        self.assertIsNone(out[2]['adjusted_serve20_diff'])
        self.assertIsNotNone(out[3]['adjusted_serve20_diff'])

    def test_ids_and_bad_stat_no_fabrication(self):
        wrong=match('2025-01-01',1)
        wrong['winner_id']=''
        bad=match('2025-01-02',1)
        bad['w_1stWon']='999'
        future=match('2025-02-10',1)
        res,rejected=build_features([wrong,bad,future],'ATP')
        self.assertEqual(len(rejected),1)
        self.assertEqual(len(res),2)
        self.assertIsNone(res[-1]['serve20_diff'])
        self.assertIsNotNone(res[-1]['elo_diff'])

    def test_missing_provider_match_number_has_safe_deterministic_id(self):
        r=match('2025-08-07',1,w='B',l='A')
        r['match_num']=''
        r['round']='R64'
        out,bad=build_features([r,r],'ATP')
        self.assertEqual(len(out),1)
        self.assertEqual(bad[0]['reason'],'DUPLICATE_MATCH_ID')
        self.assertIn('AUTO:R64:A:B',out[0]['match_id'])
        no_round=dict(r)
        no_round['round']=''
        out2,bad2=build_features([no_round],'ATP')
        self.assertFalse(out2)
        self.assertEqual(bad2[0]['reason'],'MISSING_MATCH_NUM_AND_ROUND')

    def test_retirement_rejected(self):
        r=match('2024-01-01',1)
        r['score']='4-1 RET'
        out,bad=build_features([r],'ATP')
        self.assertFalse(out)
        self.assertEqual(len(bad),1)

    def test_duplicate_match_id_rejected(self):
        r=match('2024-01-01',1)
        out,bad=build_features([r,r],'ATP')
        self.assertEqual(len(out),1)
        self.assertEqual(bad[0]['reason'],'DUPLICATE_MATCH_ID')


class EvaluationTests(unittest.TestCase):
    def test_metric(self):
        m=metrics([(0.9,1),(0.2,0)])
        self.assertEqual(m['accuracy'],1.0)
        self.assertAlmostEqual(m['brier'],0.025,places=7)

    def test_no_missing_surrogate(self):
        self.assertFalse(eligible({'elo_diff':None},ELO))
        with self.assertRaises(ValueError):
            train([{'elo_diff':None,'y':1}]*50,ELO)

    def test_platt_never_reverse_direction(self):
        p=[(0.2,0)]*40+[(0.8,1)]*40
        a,b=fit_platt(p)
        self.assertGreaterEqual(a,0)
        self.assertLess(b+a*math.log(.2/.8),b+a*math.log(.8/.2))

    def test_expanding_folds(self):
        # Synthetic functional test; NOT an accuracy claim.
        rows=[]
        for yr in (2021,2022,2023,2024):
            for j in range(130):
                rows.append({'date':f'{yr}-06-{(j%27)+1:02d}', 'match_id':f'{yr}-{j:03d}',
                             'y':int(j%2==0),'elo_diff':(j%15-7)*20.0,
                             'rank_diff':float(j%9-4), 'age_interval_diff':float(j%7-3),
                             'form20_diff':float(j%5-2)/10,'serve20_diff':float(j%7-3)/20,
                             'return20_diff':float(j%8-4)/20,'adjusted_serve20_diff':float(j%6-3)/20})
        report=walk_forward(rows,min_train=100,min_calibration=30,min_test=20)
        self.assertEqual(report['folds'][0]['test_year'],'2023')
        self.assertEqual(report['folds'][0]['calibration_year'],'2022')
        self.assertEqual(report['folds'][0]['models']['POINT']['status'],'EVALUATED')
        self.assertFalse(report['production_enabled'])

if __name__=='__main__':
    unittest.main()
