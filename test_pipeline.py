"""Offline synthetic regression tests. No source corpus or Gemini access."""
import copy
import csv
import json
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pipeline as p

PAGES = [{'page': 1, 'text': 'The method was evaluated against measurements from a demolition project.'}]
QUOTE = {'page': 1, 'quote': PAGES[0]['text'], 'role': 'evaluation'}


def response(score=3):
    return {'assessments': [{'subgroup': 'SG01', 'score': score, 'reason': 'Synthetic test evidence.',
            'limitations': '', 'visual_evidence_needs_review': False, 'pages_checked': [1],
            'evidence': [dict(QUOTE, role='contribution'), copy.deepcopy(QUOTE)]}]}


def fixture():
    records = [{'Study ID': f'S{i:02}', 'Subgroup': f'SG{j:02}', 'Assessed score': (j - 1) % 5}
               for i in range(1, 60) for j in range(1, 26)]
    studies = [{'study_id': f'S{i:02}', 'pdf': f'{i}.pdf', 'family_id': str(i),
                'split': 'calibration' if i == 1 else 'holdout', 'extraction_reviewed': True,
                'building_scope': 'yes'} for i in range(1, 60)]
    examples = [{'study_id': 'S01', 'subgroup': f'SG{i:02}', 'source_verified_by': 'test reviewer',
                 'explanation': 'DULSHAN_SECRET_EXAMPLE', 'evidence': [copy.deepcopy(QUOTE)]} for i in range(1, 6)]
    plan = {'reviewer': 'test', 'review_role': 'synthetic', 'source_and_extraction_review_complete': True,
            'split_rationale': 'synthetic', 'studies': studies, 'examples': examples}
    authority = {'dulshan': records, 'rubric_verbatim': 'EXACT_RUBRIC', 'subgroups': {f'SG{i:02}': 'requirement' for i in range(1, 26)}}
    docs = {f'{i}.pdf': {'pages': copy.deepcopy(PAGES), 'path': f'{i}.pdf', 'sha256': '0' * 64} for i in range(1, 60)}
    return {'plan': plan, 'authority': authority, 'documents': docs}


class Tests(unittest.TestCase):
    def test_valid_response(self):
        p.validate_response(response(), ['SG01'], PAGES)

    def test_fabricated_quote(self):
        r = response()
        r['assessments'][0]['evidence'][0]['quote'] = 'Invented project evidence that does not exist'
        with self.assertRaises(ValueError):
            p.validate_response(r, ['SG01'], PAGES)

    def test_invalid_page(self):
        with self.assertRaises(ValueError):
            p.check_evidence(dict(QUOTE, page=2), PAGES)

    def test_zero_requires_complete_coverage(self):
        r = response(0)
        r['assessments'][0]['pages_checked'] = []
        with self.assertRaises(ValueError):
            p.validate_response(r, ['SG01'], PAGES)

    def test_four_requires_project_evidence(self):
        with self.assertRaises(ValueError):
            p.validate_response(response(4), ['SG01'], PAGES)

    def test_duplicate_subgroup(self):
        r = response()
        r['assessments'] *= 2
        with self.assertRaises(ValueError):
            p.validate_response(r, ['SG01', 'SG02'], PAGES)

    def test_missing_subgroup(self):
        with self.assertRaises(ValueError):
            p.validate_response(response(), ['SG01', 'SG02'], PAGES)

    def test_unknown_fields(self):
        import jsonschema
        r = response()
        r['assessments'][0]['new_rubric'] = 9
        with self.assertRaises(jsonschema.ValidationError):
            p.validate_response(r, ['SG01'], PAGES)

    def test_unresolved_is_explicit(self):
        r = response(-1)
        r['assessments'][0]['evidence'] = []
        p.validate_response(r, ['SG01'], PAGES)

    def test_plan_valid_and_non_mutating(self):
        b = fixture()
        before = copy.deepcopy(b['plan']['examples'])
        p.validate_plan(b['plan'], b['authority'], b['documents'])
        self.assertEqual(b['plan']['examples'], before)

    def test_holdout_example_rejected(self):
        b = fixture()
        b['plan']['examples'][0]['study_id'] = 'S02'
        with self.assertRaises(ValueError):
            p.validate_plan(b['plan'], b['authority'], b['documents'])

    def test_family_leakage(self):
        b = fixture()
        b['plan']['studies'][1]['family_id'] = '1'
        with self.assertRaises(ValueError):
            p.validate_plan(b['plan'], b['authority'], b['documents'])

    def test_argon_and_baseline_blind(self):
        b = fixture()
        study = b['plan']['studies'][1]
        for stage in ('argon', 'baseline'):
            text = p.prompt_for(b, study, stage, {'SG01': 'requirement'})
            self.assertNotIn('DULSHAN_SECRET_EXAMPLE', text)
            self.assertIn('EXACT_RUBRIC', text)
        self.assertIn('DULSHAN_SECRET_EXAMPLE', p.prompt_for(b, study, 'flash', {'SG01': 'requirement'}))

    def test_own_family_examples_omitted(self):
        b = fixture()
        self.assertNotIn('DULSHAN_SECRET_EXAMPLE', p.prompt_for(b, b['plan']['studies'][0], 'flash', {'SG01': 'requirement'}))

    def test_atomic_io(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.json'
            p.write(path, {'first': True})
            p.write(path, {'second': True})
            self.assertEqual(p.read(path), {'second': True})

    def test_lock_conflict_and_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.lock'
            with p.lock(path):
                with self.assertRaises(ValueError):
                    with p.lock(path):
                        pass
            self.assertFalse(path.exists())

    def test_bundle_tamper(self):
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'WORK', Path(d)):
            b = {'code': p.code_identity(), 'authority': {'sources': {}}, 'documents': {}}
            identity = p.digest(b)
            path = Path(d) / 'versions' / identity / 'bundle.json'
            p.write(path, b)
            self.assertEqual(p.bundle_for(identity), b)
            b['extra'] = True
            p.write(path, b)
            with self.assertRaises(ValueError):
                p.bundle_for(identity)

    def test_live_requires_explicit_flag(self):
        with self.assertRaises(ValueError):
            p.assess(SimpleNamespace(allow_api=False))


class WorkflowTests(unittest.TestCase):
    def test_interrupted_assessment_resumes_without_repeating_saved_batch(self):
        b = fixture()
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'WORK', Path(d)):
            pdf = Path(d) / 'fixture.pdf'
            pdf.write_bytes(b'%PDF synthetic test payload only')
            b['documents']['2.pdf'].update(path=str(pdf), sha256=p.file_hash(pdf))
            calls = []

            def generate(pin, system, parts, **kwargs):
                groups = json.loads(system.split('SUBGROUPS\n')[1])
                calls.append(list(groups))
                if len(calls) == 2:
                    raise RuntimeError('Synthetic interruption')
                rows = []
                for sg in groups:
                    row = copy.deepcopy(response()['assessments'][0])
                    row['subgroup'] = sg
                    rows.append(row)
                return {'assessments': rows}

            client = MagicMock()
            client.generate_json.side_effect = generate
            client.stats.return_value = {'calls': 1}
            args = SimpleNamespace(allow_api=True, max_calls=5, version='a' * 64, stage='baseline', studies='S02', retry_rejected=False)
            with patch.object(p, 'bundle_for', return_value=b), patch('vendor.gemini.GeminiClient', return_value=client):
                with self.assertRaises(RuntimeError):
                    p.assess(args)
                p.assess(args)
            self.assertEqual(len(calls), 6)
            self.assertEqual(sum('SG01' in group for group in calls), 1)
            saved = sorted((Path(d) / 'versions' / args.version / 'results/baseline').glob('*.json'))
            self.assertEqual(len(saved), 5)
            result = p.collect_results(b, args.version)
            self.assertEqual(len(result), 25)
            record = p.read(saved[0])
            record['response']['assessments'][0]['score'] = 0
            p.write(saved[0], record)
            with self.assertRaises(ValueError):
                p.collect_results(b, args.version)

    def test_resume_validates_prompt_and_config_identities(self):
        b = fixture()
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'WORK', Path(d)):
            pdf = Path(d) / 'fixture.pdf'
            pdf.write_bytes(b'%PDF synthetic test payload only')
            b['documents']['2.pdf'].update(path=str(pdf), sha256=p.file_hash(pdf))

            def generate(pin, system, parts, **kwargs):
                groups = json.loads(system.split('SUBGROUPS\n')[1])
                rows = []
                for sg in groups:
                    row = copy.deepcopy(response()['assessments'][0])
                    row['subgroup'] = sg
                    rows.append(row)
                return {'assessments': rows}

            client = MagicMock()
            client.generate_json.side_effect = generate
            client.stats.return_value = {'calls': 1}
            args = SimpleNamespace(allow_api=True, max_calls=1, version='a' * 64, stage='baseline', studies='S02', retry_rejected=False)
            with patch.object(p, 'bundle_for', return_value=b), patch('vendor.gemini.GeminiClient', return_value=client):
                p.assess(args)
                saved_file = Path(d) / 'versions' / args.version / 'results/baseline/S02_1.json'
                rec = p.read(saved_file)
                # Tamper with prompt_hash and re-sign record_hash: resume MUST reject prompt drift.
                bad_prompt = copy.deepcopy(rec)
                bad_prompt.pop('record_hash', None)
                bad_prompt['prompt_hash'] = 'f' * 64
                bad_prompt['record_hash'] = p.digest(bad_prompt)
                p.write(saved_file, bad_prompt)
                with self.assertRaises(ValueError):
                    p.assess(args)
                # Restore prompt_hash, tamper with model_settings (e.g. 32768 vs 65536): resume MUST reject config drift.
                bad_cfg = copy.deepcopy(rec)
                bad_cfg.pop('record_hash', None)
                bad_cfg['model_settings'] = dict(bad_cfg['model_settings'], max_output_tokens=32768)
                bad_cfg['record_hash'] = p.digest(bad_cfg)
                p.write(saved_file, bad_cfg)
                with self.assertRaises(ValueError):
                    p.assess(args)

    def test_finalize_requires_both_models(self):
        with patch.object(p, 'bundle_for', return_value=fixture()), patch.object(p, 'collect_results', return_value={}):
            with self.assertRaises(ValueError):
                p.finalize(SimpleNamespace(version='a' * 64))

    def test_finalize_profiles_exclude_outside_scope_and_preserve_zero(self):
        b = fixture()
        b['plan']['studies'][-1]['building_scope'] = 'no'
        complete = {(stage, r['Study ID'], r['Subgroup']): {} for stage in ('flash', 'argon') for r in b['authority']['dulshan']}
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'WORK', Path(d)):
            sheet = Path(d) / 'review.csv'
            rows = [{'version': 'a' * 64, 'study_id': r['Study ID'], 'subgroup': r['Subgroup'],
                     'dulshan': r['Assessed score'], 'reviewed_score': r['Assessed score'], 'reviewer': 'Synthetic reviewer',
                     'decision_reason': 'Synthetic source-reviewed decision'} for r in b['authority']['dulshan']]
            with sheet.open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
            args = SimpleNamespace(version='a' * 64, review_sheet=sheet)
            with patch.object(p, 'bundle_for', return_value=b), patch.object(p, 'collect_results', return_value=complete), patch.object(p, 'verify_independent_review_lock', return_value='f' * 64):
                p.finalize(args)
                final = p.read(next((Path(d) / 'versions' / args.version / 'final').glob('*.json')))
                self.assertEqual(len(final['decisions']), 1475)
                self.assertEqual(final['profiles'][0]['denominator'], 58)
                self.assertEqual(final['profiles'][0]['score_counts']['0'], 58)
                self.assertEqual(final['profiles'][4]['project_observations_percent'], 100)
                self.assertEqual(final['profiles'][2]['evaluation_percent'], 0)
                sheet.write_text(sheet.read_text(encoding='utf-8').replace('a' * 64, 'b' * 64), encoding='utf-8')
                with self.assertRaises(ValueError):
                    p.finalize(args)

    def test_blind_review_lock_required_and_verified(self):
        version = 'a' * 64
        subgroups = fixture()['authority']['subgroups']
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'WORK', Path(d)):
            private = p.WORK / 'review/private_keys'
            sheet = p.WORK / 'review/blind_reviewer_packet/blind_reviewer_scoring_sheet.csv'
            sheet.parent.mkdir(parents=True)
            aliases = [f'BLIND_STUDY_{i:02}' for i in range(1, 6)]
            rows = [{'blind_study_id': a, 'subgroup_id': sg, 'reviewed_score': '1',
                     'justification_rationale': 'Independent review'} for a in aliases for sg in subgroups]
            with sheet.open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
            p.write(private / 'private_mapping.json', {'sealed_version': version, 'mapping': {a: {} for a in aliases}})
            status = {'sealed_version': version, 'locked': False, 'completed_by': None, 'locked_timestamp': None,
                      'locked_scoring_sheet_sha256': None}
            p.write(private / 'independent_review_status.json', status)
            with self.assertRaisesRegex(ValueError, 'completed, signed and locked'):
                p.verify_independent_review_lock(version, subgroups)
            status.update(locked=True, completed_by='Independent reviewer', locked_timestamp='2026-11-09T00:00:00Z',
                          locked_scoring_sheet_sha256=p.file_hash(sheet))
            p.write(private / 'independent_review_status.json', status)
            self.assertEqual(p.verify_independent_review_lock(version, subgroups), p.file_hash(sheet))
            sheet.write_text(sheet.read_text(encoding='utf-8') + '\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'locked SHA-256'):
                p.verify_independent_review_lock(version, subgroups)

    def test_started_blind_review_is_not_overwritten(self):
        import build_review_packets as packets
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); blind = root / 'packet'; private = root / 'private'; blind.mkdir(); private.mkdir()
            sheet = blind / 'blind_reviewer_scoring_sheet.csv'
            fields = ['reviewed_score', 'cited_pdf_page', 'verbatim_evidence_quote',
                      'justification_rationale', 'visual_evidence_needs_review', 'notes_or_uncertainty']
            def write_row(score):
                with sheet.open('w', newline='', encoding='utf-8') as f:
                    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerow({'reviewed_score': score})
            write_row(''); packets.ensure_review_packet_not_started(blind, private)
            write_row('0')
            with self.assertRaisesRegex(ValueError, 'has started'):
                packets.ensure_review_packet_not_started(blind, private)
            write_row(''); p.write(private / 'independent_review_status.json', {'locked': True})
            with self.assertRaisesRegex(ValueError, 'locked'):
                packets.ensure_review_packet_not_started(blind, private)
            queue = root / 'adjudication_queue.csv'
            fields = ['final_human_adjudicated_score', 'human_adjudicator_name',
                      'adjudication_decision_rationale', 'sign_off_date']
            with queue.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerow({'final_human_adjudicated_score': '0'})
            with self.assertRaisesRegex(ValueError, 'adjudication has started'):
                packets.ensure_adjudication_not_started(queue)

    def test_sealed_inputs_can_be_relocated(self):
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'WORK', Path(d) / 'work'):
            root = Path(d)
            for name in ('source_a', 'source_b'):
                target = root / name / 'papers/test.pdf'
                target.parent.mkdir(parents=True)
                target.write_bytes(b'synthetic identical PDF content')
            doc = {'path': 'papers/test.pdf', 'sha256': p.file_hash(root / 'source_a/papers/test.pdf')}
            b = {'code': p.code_identity(), 'authority': {'sources': {}}, 'documents': {'test.pdf': doc},
                 'runtime': p.runtime_identity()}
            identity = p.digest(b)
            p.write(p.WORK / 'versions' / identity / 'bundle.json', b)
            for name in ('source_a', 'source_b'):
                with patch.object(p, 'SOURCE', root / name):
                    self.assertEqual(p.bundle_for(identity), b)
            with patch.object(p, 'SOURCE', root / 'source_b'), patch.object(p, 'runtime_identity', return_value={}):
                with self.assertRaises(ValueError):
                    p.bundle_for(identity)


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.pages = [
            {'page': 1, 'text': 'The circular economy framework was applied to the deconstruction of a four-\nstory modular building system pro\xad\nject located in Melbourne.'},
            {'page': 2, 'text': 'Subsequent structural appraisals confirmed component reusability across multiple lifecycles.'},
            {'page': 3, 'text': 'The method was never evaluated against measurements from a demolition project.'},
        ]

    def test_fabricated_token_rejected(self):
        quote = {'page': 1, 'quote': 'The circular economy framework was heavily applied to the deconstruction', 'role': 'contribution'}
        with self.assertRaises(ValueError):
            p.check_evidence(quote, self.pages)

    def test_spliced_sentences_rejected(self):
        quote = {'page': 1, 'quote': 'The circular economy framework was applied to component reusability across multiple lifecycles.', 'role': 'contribution'}
        with self.assertRaises(ValueError):
            p.check_evidence(quote, self.pages)

    def test_omitted_never_reversing_meaning_rejected(self):
        # Previously accepted by the 400-character gap split loop; must now be strictly rejected as unverified.
        quote = {'page': 3, 'quote': 'The method was evaluated against measurements from a demolition project.', 'role': 'evaluation'}
        with self.assertRaises(ValueError):
            p.check_evidence(quote, self.pages)
        self.assertEqual(quote['match_status'], 'unverified')

    def test_wrong_page_quote_rejected_including_adjacent_page(self):
        # Quote wholly on page 2 attributed to adjacent page 1 must NOT pass as cross_page_contiguous.
        adj_quote = {'page': 1, 'quote': 'Subsequent structural appraisals confirmed component reusability across multiple lifecycles.', 'role': 'evaluation'}
        with self.assertRaises(ValueError):
            p.check_evidence(adj_quote, self.pages)
        self.assertEqual(adj_quote['match_status'], 'wrong_page')
        self.assertEqual(adj_quote['matched_pages'], [2])

        # Quote wholly on page 3 attributed to distant page 1 must also be rejected as wrong_page.
        far_quote = {'page': 1, 'quote': 'The method was never evaluated against measurements from a demolition project.', 'role': 'gap'}
        with self.assertRaises(ValueError):
            p.check_evidence(far_quote, self.pages)
        self.assertEqual(far_quote['match_status'], 'wrong_page')
        self.assertEqual(far_quote['matched_pages'], [3])

    def test_uncertain_layout_routed_to_review_not_accepted(self):
        layout_pages = [{'page': 1, 'text': 'The modular building staﬀkitchen was dismantled carefully on site.'}]
        quote = {'page': 1, 'quote': 'modular building staff kitchen was dismantled carefully', 'role': 'project'}
        with self.assertRaises(ValueError):
            p.check_evidence(quote, layout_pages)
        self.assertEqual(quote['match_status'], 'uncertain_layout')
        self.assertEqual(quote['matched_pages'], [1])

    def test_soft_hyphen_and_line_wrap_normalization_accepted(self):
        quote = {'page': 1, 'quote': 'four-story modular building system project located in Melbourne.', 'role': 'project'}
        res = p.check_evidence(quote, self.pages)
        self.assertIn(res['status'], ('normalized_contiguous', 'exact'))
        self.assertEqual(quote['matched_pages'], [1])
        self.assertTrue(len(quote['char_spans']) >= 1)

    def test_numerical_omissions_and_truncations_blocked(self):
        num_pages = [
            {'page': 1, 'text': 'Conventional manual dismantling required\n408\nhours across the three-storey masonry dwelling.'},
            {'page': 2, 'text': 'The circular economy framework was applied to a four-story\n801\nmodular building system in Hong Kong.'},
            {'page': 3, 'text': 'In 0.25% of the cases considered only sub-optimal solutions were obtained, with a -15% change in duration.'},
        ]
        bad_quotes = [
            # Standalone line-wrapped integer omitted (previously stripped by \n[0-9]+\n regex)
            {'page': 1, 'quote': 'Conventional manual dismantling required hours across the three-storey', 'role': 'project'},
            {'page': 2, 'quote': 'applied to a four-story modular building system in Hong Kong.', 'role': 'project'},
            # Mid-number / decimal / sign / percentage slicing at quote boundaries
            {'page': 1, 'quote': '8 hours across the three-storey masonry dwelling.', 'role': 'project'},
            {'page': 1, 'quote': 'Conventional manual dismantling required 40', 'role': 'project'},
            {'page': 3, 'quote': '25% of the cases considered only sub-optimal solutions were obtained', 'role': 'evaluation'},
            {'page': 3, 'quote': 'In 0.25 of the cases considered only sub-optimal solutions', 'role': 'evaluation'},
            {'page': 3, 'quote': '15% change in duration.', 'role': 'evaluation'},
            # Inline numerical omission or alteration
            {'page': 3, 'quote': 'In % of the cases considered only sub-optimal solutions were obtained', 'role': 'evaluation'},
            {'page': 1, 'quote': 'Conventional manual dismantling required 400 hours across the three-storey', 'role': 'project'},
        ]
        for q in bad_quotes:
            with self.subTest(quote=q['quote']):
                with self.assertRaises(ValueError):
                    p.check_evidence(dict(q), num_pages)

    def test_cross_page_quote_accepted_with_indices(self):
        quote = {'page': 1, 'quote': 'project located in Melbourne. Subsequent structural appraisals confirmed component', 'role': 'project'}
        res = p.check_evidence(quote, self.pages)
        self.assertEqual(res['status'], 'cross_page_contiguous')
        self.assertEqual(quote['matched_pages'], [1, 2])
        self.assertEqual(len(quote['char_spans']), 2)

    def test_we_propose_fallback_removed(self):
        pages = [{'page': 1, 'text': 'To address this issue, we propose a new framework.'}]
        r = {'assessments': [{'subgroup': 'SG01', 'score': 2, 'reason': 'Test justification',
                              'limitations': '', 'visual_evidence_needs_review': False,
                              'pages_checked': [1],
                              'evidence': [{'page': 1, 'quote': 'To address this issue, we propose a new framework.', 'role': 'gap'}]}]}
        with self.assertRaises(ValueError):
            p.validate_response(r, ['SG01'], pages)

    def test_reference_only_score_4_routing(self):
        b = fixture()
        b['authority']['dulshan'] = [{'Study ID': 'S54', 'Subgroup': 'SG21', 'Assessed score': 4}]
        b['plan']['studies'] = [{'study_id': 'S54', 'pdf': '1.pdf', 'family_id': 'YANG', 'split': 'holdout',
                                 'extraction_reviewed': True, 'building_scope': 'yes'}]
        results = {
            ('baseline', 'S54', 'SG21'): {'score': 0, 'reason': 'r', 'evidence': []},
            ('flash', 'S54', 'SG21'): {'score': 0, 'reason': 'r', 'evidence': []},
            ('argon', 'S54', 'SG21'): {'score': 1, 'reason': 'r', 'evidence': []}
        }
        with tempfile.TemporaryDirectory() as d:
            with patch.object(p, 'WORK', Path(d)), patch.object(p, 'bundle_for', return_value=b), patch.object(p, 'collect_results', return_value=results):
                args = types.SimpleNamespace(version='a' * 64)
                p.export(args)
                csv_path = next((Path(d) / 'versions' / args.version / 'exports').glob('comparison_*.csv'))
                with csv_path.open(encoding='utf-8-sig', newline='') as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 1)
                self.assertIn('human_score_4', rows[0]['review_flags'])
                self.assertIn('score_disagreement', rows[0]['review_flags'])

    def test_approved_production_selection_and_rejection(self):
        b = fixture()
        cal_ids = {'S01', 'S04', 'S08', 'S09', 'S10', 'S11', 'S17', 'S19', 'S20', 'S31', 'S49', 'S51'}
        hold_ids = {'S02', 'S03', 'S14', 'S28', 'S29', 'S32', 'S45', 'S46', 'S47', 'S50', 'S53', 'S54'}
        out_of_scope = {'S47', 'S51', 'S55', 'S57'}
        for s in b['plan']['studies']:
            sid = s['study_id']
            s['split'] = 'calibration' if sid in cal_ids else ('holdout' if sid in hold_ids else 'production')
            s['building_scope'] = 'no' if sid in out_of_scope else 'yes'

        prod_all = p.approved_studies(b, 'production', eligible_only=False)
        prod_elig = p.approved_studies(b, 'production', eligible_only=True)
        self.assertEqual(len(prod_all), 35)
        self.assertEqual(len(prod_elig), 33)
        self.assertEqual(set(prod_all) - set(prod_elig), {'S55', 'S57'})
        for wrong_cal in ('S04', 'S08', 'S09', 'S11', 'S17', 'S19', 'S20', 'S31', 'S51'):
            self.assertNotIn(wrong_cal, prod_all)
        for req_prod in ('S06', 'S18', 'S22', 'S48', 'S52', 'S56', 'S57', 'S58', 'S59'):
            self.assertIn(req_prod, prod_all)

        # Erroneous manual list mixing calibration and omitting 9 production studies MUST be rejected.
        erroneous = sorted((set(prod_all) - {'S06', 'S18', 'S22', 'S48', 'S52', 'S56', 'S57', 'S58', 'S59'})
                           | {'S04', 'S08', 'S09', 'S11', 'S17', 'S19', 'S20', 'S31', 'S51'})
        with self.assertRaises(ValueError):
            p.resolve_requested_studies(b, SimpleNamespace(split='production', studies=','.join(erroneous), pilot_subset=False, eligible_only=False))
        with self.assertRaises(ValueError):
            p.resolve_requested_studies(b, SimpleNamespace(split=None, studies=','.join(erroneous), pilot_subset=False, eligible_only=False))
        # Partial production list without --pilot-subset MUST be rejected.
        with self.assertRaises(ValueError):
            p.resolve_requested_studies(b, SimpleNamespace(split='production', studies='S05,S06', pilot_subset=False, eligible_only=False))
        # Bounded pilot with --pilot-subset within production MUST succeed.
        pilot = p.resolve_requested_studies(b, SimpleNamespace(split='production', studies='S05,S06', pilot_subset=True, eligible_only=False))
        self.assertEqual([s['study_id'] for s in pilot], ['S05', 'S06'])

    def test_historical_import_preserves_original_seal_and_failed_assessments(self):
        b = fixture()
        old_ver = '1' * 64
        new_ver = '2' * 64
        sg_ids = sorted(b['authority']['subgroups'])
        study = next(s for s in b['plan']['studies'] if s['study_id'] == 'S02')
        cfg = p.model_config('flash')

        with tempfile.TemporaryDirectory() as d, patch.object(p, 'WORK', Path(d)):
            # Batch 1: valid quotes + matching prompt/config -> should import as accepted .json
            grp1 = {sg: b['authority']['subgroups'][sg] for sg in sg_ids[:5]}
            ph1 = p.digest(p.prompt_for(b, study, 'flash', grp1))
            rows1 = [dict(copy.deepcopy(response(3)['assessments'][0]), subgroup=sg) for sg in grp1]
            rec1 = {
                'version': old_ver, 'stage': 'flash', 'study_id': 'S02',
                'model': cfg['id'], 'model_settings': cfg, 'prompt_hash': ph1,
                'response': {'assessments': rows1}, 'cumulative_usage': {},
            }
            rec1['record_hash'] = p.digest(rec1)
            p.write(Path(d) / 'versions' / old_ver / 'results/flash/S02_1.json', rec1)

            # Batch 2: unverified quote on SG06 -> should be preserved as reviewable .rejected.json
            grp2 = {sg: b['authority']['subgroups'][sg] for sg in sg_ids[5:10]}
            ph2 = p.digest(p.prompt_for(b, study, 'flash', grp2))
            rows2 = [dict(copy.deepcopy(response(3)['assessments'][0]), subgroup=sg) for sg in grp2]
            rows2[0]['evidence'][0]['quote'] = 'Invented non-existent quotation text on page one'
            rec2 = {
                'version': old_ver, 'stage': 'flash', 'study_id': 'S02',
                'model': cfg['id'], 'model_settings': cfg, 'prompt_hash': ph2,
                'response': {'assessments': rows2}, 'cumulative_usage': {},
            }
            rec2['record_hash'] = p.digest(rec2)
            p.write(Path(d) / 'versions' / old_ver / 'results/flash/S02_2.json', rec2)

            prov_path = Path(d) / 'prov.json'
            p.write(prov_path, {'batches': [
                {'stage': 'flash', 'study_id': 'S02', 'batch_index': 1, 'original_execution_seal': '0' * 64,
                 'request_cache_key': 'ck1', 'raw_cache_path': 'work/cache/raw/ck1.json', 'raw_cache_sha256': '3' * 64},
                {'stage': 'flash', 'study_id': 'S02', 'batch_index': 2, 'original_execution_seal': '0' * 64,
                 'request_cache_key': 'ck2', 'raw_cache_path': 'work/cache/raw/ck2.json', 'raw_cache_sha256': '4' * 64},
            ]})

            with patch.object(p, 'bundle_for', return_value=b):
                p.import_historical(SimpleNamespace(from_version=old_ver, to_version=new_ver, provenance=prov_path))
                acc1 = p.read(Path(d) / 'versions' / new_ver / 'results/flash/S02_1.json')
                self.assertEqual(acc1['original_execution_seal'], '0' * 64)
                self.assertEqual(acc1['imported_from_version'], old_ver)
                self.assertTrue((Path(d) / 'versions' / new_ver / 'results/flash/S02_2.rejected.json').exists())

                p.export(SimpleNamespace(version=new_ver))
                csv_path = next((Path(d) / 'versions' / new_ver / 'exports').glob('comparison_*.csv'))
                with csv_path.open(encoding='utf-8-sig', newline='') as f:
                    exported = {(r['study_id'], r['subgroup']): r for r in csv.DictReader(f)}
                self.assertEqual(exported[('S02', 'SG01')]['flash_status'], 'accepted')
                self.assertEqual(exported[('S02', 'SG06')]['flash_status'], 'rejected_evidence')
                self.assertEqual(exported[('S02', 'SG06')]['flash'], '3')
                self.assertIn('flash_evidence_unverified', exported[('S02', 'SG06')]['review_flags'])
                self.assertIn('flash_batch_rejected', exported[('S02', 'SG06')]['review_flags'])


class BudgetAndAttemptProtectionTests(unittest.TestCase):
    """Offline tests proving excess provider attempts and excess USD spending are strictly blocked."""

    @staticmethod
    def _mock_provider_response(payload_obj, finish_reason='STOP', prompt_tok=25000,
                                cached_tok=0, cand_tok=1500, thought_tok=3500):
        resp = MagicMock()
        resp.text = json.dumps(payload_obj)
        resp.model_dump_json.return_value = json.dumps({'mock': True, 'finish_reason': finish_reason})
        cand = SimpleNamespace(finish_reason=finish_reason)
        resp.candidates = [cand]
        resp.usage_metadata = SimpleNamespace(
            prompt_token_count=prompt_tok,
            cached_content_token_count=cached_tok,
            candidates_token_count=cand_tok,
            thoughts_token_count=thought_tok,
        )
        return resp

    def test_excess_provider_attempts_blocked_during_retries(self):
        from vendor.gemini import GeminiClient, BudgetExceededError
        cfg = p.model_config('flash')  # max_retries == 4
        pricing = p.model_pricing(cfg['id'])
        with tempfile.TemporaryDirectory() as d:
            mock_sdk = MagicMock()
            mock_sdk.models.generate_content.side_effect = RuntimeError('503 UNAVAILABLE')
            with patch('vendor.gemini.genai.Client', return_value=mock_sdk), patch('vendor.gemini.time.sleep'):
                client = GeminiClient(cfg, Path(d) / 'cache', keys=['synthetic-key'],
                                      pricing=pricing, max_attempts=3, max_cost_usd=5.0)
                client.set_evidence('pin1', {'pdf': '0' * 64})
                with self.assertRaises(BudgetExceededError):
                    client.generate_json('pin1', 'system prompt', ['[PDF PAGE 1]\ntext'], schema=p.provider_schema())
            # Strictly 3 live attempts made; the 4th retry attempt was blocked pre-call.
            self.assertEqual(mock_sdk.models.generate_content.call_count, 3)
            self.assertEqual(client.stats()['provider_attempts'], 3)

    def test_excess_provider_attempts_blocked_across_stages_via_shared_budget_file(self):
        from vendor.gemini import BudgetExceededError
        b = fixture()
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'WORK', Path(d)):
            pdf = Path(d) / 'fixture.pdf'
            pdf.write_bytes(b'%PDF synthetic test payload')
            b['documents']['2.pdf'].update(path=str(pdf), sha256=p.file_hash(pdf))
            budget_file = Path(d) / 'pilot_budget.json'

            attempt_counter = {'count': 0}

            def fake_generate_content(model, contents, config):
                attempt_counter['count'] += 1
                # Simulate one transient 503 on the very first provider attempt so Batch 1 consumes 2 attempts.
                if attempt_counter['count'] == 1:
                    raise RuntimeError('503 UNAVAILABLE')
                sys_inst = config.system_instruction or ''
                groups = json.loads(sys_inst.split('SUBGROUPS\n')[1].split('\nSource-verified')[0])
                rows = [dict(copy.deepcopy(response(3)['assessments'][0]), subgroup=sg) for sg in groups]
                return self._mock_provider_response({'assessments': rows})

            mock_sdk = MagicMock()
            mock_sdk.models.generate_content.side_effect = fake_generate_content

            with patch.object(p, 'bundle_for', return_value=b), \
                 patch.object(p, 'SOURCE', Path('/')), \
                 patch('vendor.gemini.genai.Client', return_value=mock_sdk), \
                 patch('vendor.gemini.collect_keys', return_value=['synthetic-key']), \
                 patch('vendor.gemini.time.sleep'):
                # Stage 1 (flash): max_calls=2 -> Batch 1 uses 2 attempts (1 retry + 1 ok), Batch 2 uses 1 attempt = 3 total.
                args_flash = SimpleNamespace(
                    allow_api=True, max_calls=2, max_attempts=4, max_cost_usd=5.0,
                    budget_file=budget_file, max_retries=None,
                    version='a' * 64, stage='flash', studies='S02', retry_rejected=False,
                )
                p.assess(args_flash)
                self.assertEqual(attempt_counter['count'], 3)

                # Stage 2 (argon) sharing the SAME budget_file (max_attempts=4):
                # Argon Batch 1 uses attempt #4 (allowed); Argon Batch 2 would be attempt #5 -> BLOCKED!
                args_argon = SimpleNamespace(
                    allow_api=True, max_calls=2, max_attempts=4, max_cost_usd=5.0,
                    budget_file=budget_file, max_retries=None,
                    version='a' * 64, stage='argon', studies='S02', retry_rejected=False,
                )
                with self.assertRaises(BudgetExceededError):
                    p.assess(args_argon)

                # Re-running flash when S02_1 and S02_2 are already saved skips S02_1/S02_2 (0 attempts)
                # and immediately blocks S02_3 because provider_attempts is already at ceiling (4/4).
                with self.assertRaises(BudgetExceededError):
                    p.assess(args_flash)

            self.assertEqual(attempt_counter['count'], 4)
            ledger = p.read(budget_file)
            self.assertEqual(ledger['provider_attempts'], 4)
            self.assertTrue((Path(d) / 'versions' / ('a' * 64) / 'results/argon/S02_1.json').exists())
            self.assertFalse((Path(d) / 'versions' / ('a' * 64) / 'results/argon/S02_2.json').exists())

    def test_excess_spending_blocked_pre_call_and_bills_thinking_and_truncated_responses(self):
        from vendor.gemini import GeminiClient, BudgetExceededError
        cfg = p.model_config('argon')
        pricing = p.model_pricing(cfg['id'])

        with tempfile.TemporaryDirectory() as d:
            mock_sdk = MagicMock()
            with patch('vendor.gemini.genai.Client', return_value=mock_sdk):
                # 1. Ceiling too small for even a single worst-case 65,536-token Argon call (~$0.69) -> blocked with 0 calls!
                tight_client = GeminiClient(cfg, Path(d) / 'cache_tight', keys=['synthetic-key'],
                                            pricing=pricing, max_attempts=20, max_cost_usd=0.10)
                tight_client.set_evidence('pin_tight', {'pdf': '0' * 64})
                with self.assertRaises(BudgetExceededError):
                    tight_client.generate_json('pin_tight', 'system prompt', ['[PDF PAGE 1]\ntext'], schema=p.provider_schema())
                self.assertEqual(mock_sdk.models.generate_content.call_count, 0)

            # 2. Enforced $5.00 ceiling across retries and batches, accounting for thoughts_token_count and MAX_TOKENS responses:
            budget_file = Path(d) / 'spend_budget.json'
            valid_payload = response(3)
            # Call 1: truncated MAX_TOKENS response costing $2.40 (100k in=$0.20 + 220k out+thoughts=$2.20) -> MUST still be billed!
            r1_trunc = self._mock_provider_response(
                valid_payload, finish_reason='MAX_TOKENS',
                prompt_tok=100_000, cached_tok=0, cand_tok=20_000, thought_tok=200_000,
            )
            # Call 2 (retry): valid STOP response costing $2.20 (100k in=$0.20 + 200k out+thoughts=$2.00) -> cumulative settled = $4.60.
            r2_ok = self._mock_provider_response(
                valid_payload, finish_reason='STOP',
                prompt_tok=100_000, cached_tok=0, cand_tok=20_000, thought_tok=180_000,
            )
            mock_sdk2 = MagicMock()
            mock_sdk2.models.generate_content.side_effect = [r1_trunc, r2_ok, r2_ok]

            with patch('vendor.gemini.genai.Client', return_value=mock_sdk2), patch('vendor.gemini.time.sleep'):
                client = GeminiClient(cfg, Path(d) / 'cache_5usd', keys=['synthetic-key'],
                                      pricing=pricing, max_attempts=20, max_cost_usd=5.00, budget_file=budget_file)
                client.set_evidence('pin_spend', {'pdf': '0' * 64})
                out1 = client.generate_json('pin_spend', 'system prompt', ['[PDF PAGE 1]\ntext'],
                                            variant=0, schema=p.provider_schema())
                self.assertEqual(out1['assessments'][0]['score'], 3)
                self.assertEqual(mock_sdk2.models.generate_content.call_count, 2)

                # Call 3 (variant=1): settled=$4.60 + next worst-case (~$0.69) = $5.29 > $5.00 -> BLOCKED BEFORE provider call!
                with self.assertRaises(BudgetExceededError):
                    client.generate_json('pin_spend', 'system prompt', ['[PDF PAGE 1]\ntext'],
                                         variant=1, schema=p.provider_schema())

            self.assertEqual(mock_sdk2.models.generate_content.call_count, 2)
            ledger = p.read(budget_file)
            self.assertAlmostEqual(ledger['settled_cost_usd'], 4.60, places=4)
            self.assertLessEqual(ledger['settled_cost_usd'], 5.00)
            self.assertEqual(ledger['tokens']['thought_tokens'], 380_000)

    def test_rejected_batch_call_counting_and_subsequent_batch(self):
        """Verify that a rejected batch increments calls exactly once, allowing max_calls=2 to process both."""
        b = fixture()
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'WORK', Path(d)):
            pdf = Path(d) / 'fixture.pdf'
            pdf.write_bytes(b'%PDF synthetic test payload only')
            b['documents']['2.pdf'].update(path=str(pdf), sha256=p.file_hash(pdf))
            calls = []

            def generate(pin, system, parts, **kwargs):
                groups = json.loads(system.split('SUBGROUPS\n')[1])
                calls.append(list(groups))
                rows = []
                for sg in groups:
                    row = copy.deepcopy(response()['assessments'][0])
                    row['subgroup'] = sg
                    if len(calls) == 1:
                        # Batch 1: invalid unverified quote that fails validation
                        row['evidence'][0]['quote'] = 'Fabricated non-existent quote'
                    rows.append(row)
                return {'assessments': rows}

            client = MagicMock()
            client.generate_json.side_effect = generate
            client.stats.return_value = {'calls': 1}
            args = SimpleNamespace(allow_api=True, max_calls=2, version='a' * 64, stage='baseline',
                                   studies='S02', retry_rejected=False)
            with patch.object(p, 'bundle_for', return_value=b), patch('vendor.gemini.GeminiClient', return_value=client):
                p.assess(args)

            # Both batches were called because batch 1 counted as 1 call, not 2
            self.assertEqual(len(calls), 2)
            res_dir = Path(d) / 'versions' / args.version / 'results/baseline'
            self.assertTrue((res_dir / 'S02_1.rejected.json').exists())
            self.assertTrue((res_dir / 'S02_2.json').exists())

    def test_resume_validates_rejected_record_integrity(self):
        """Verify that resuming assess rejects empty or malformed rejected records."""
        b = fixture()
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'WORK', Path(d)):
            pdf = Path(d) / 'fixture.pdf'
            pdf.write_bytes(b'%PDF synthetic test payload only')
            b['documents']['2.pdf'].update(path=str(pdf), sha256=p.file_hash(pdf))
            res_dir = Path(d) / 'versions' / ('a' * 64) / 'results/baseline'
            res_dir.mkdir(parents=True, exist_ok=True)
            rej_path = res_dir / 'S02_1.rejected.json'

            # 1. Empty {} file must produce an explicit ValueError
            p.write(rej_path, {})
            client = MagicMock()
            args = SimpleNamespace(allow_api=True, max_calls=1, version='a' * 64, stage='baseline',
                                   studies='S02', retry_rejected=False)
            with patch.object(p, 'bundle_for', return_value=b), patch('vendor.gemini.GeminiClient', return_value=client):
                with self.assertRaises(ValueError) as cm:
                    p.assess(args)
                self.assertIn('missing outer envelope', str(cm.exception))

            # Helper to create a valid baseline rejected payload
            study = next(s for s in b['plan']['studies'] if s['study_id'] == 'S02')
            sg5 = sorted(b['authority']['subgroups'])[:5]
            group = {sg: b['authority']['subgroups'][sg] for sg in sg5}
            sys_prompt = p.prompt_for(b, study, 'baseline', group)
            ph = p.digest(sys_prompt)
            cfg = p.model_config('baseline')

            def make_valid_payload():
                rec = {
                    'version': 'a' * 64,
                    'original_execution_seal': 'a' * 64,
                    'stage': 'baseline',
                    'study_id': 'S02',
                    'source_pdf': str(pdf),
                    'source_pdf_sha256': p.file_hash(pdf),
                    'model': cfg['id'],
                    'model_settings': cfg,
                    'prompt_hash': ph,
                    'response': {'assessments': [{'subgroup': sg, 'score': 0} for sg in sg5]},
                }
                rec['record_hash'] = p.digest(rec)
                payload = {
                    'record': rec,
                    'validation_error': 'Synthetic failure',
                    'failure_reasons': ['evidence_or_schema_validation_failed'],
                }
                payload['rejected_hash'] = p.digest(payload)
                return payload

            # 2. Record with mismatched stage must fail
            bad_stage = make_valid_payload()
            bad_stage['record']['stage'] = 'wrong_stage'
            bad_stage['record']['record_hash'] = p.digest({k: v for k, v in bad_stage['record'].items() if k != 'record_hash'})
            bad_stage['rejected_hash'] = p.digest({k: v for k, v in bad_stage.items() if k != 'rejected_hash'})
            p.write(rej_path, bad_stage)
            with patch.object(p, 'bundle_for', return_value=b), patch('vendor.gemini.GeminiClient', return_value=client):
                with self.assertRaises(ValueError) as cm:
                    p.assess(args)
                self.assertIn('stage or study_id mismatch', str(cm.exception))

            # 3. Tampered score with original invalid rejected_hash must fail
            tampered = make_valid_payload()
            orig_hash = tampered['rejected_hash']
            tampered['record']['response']['assessments'][0]['score'] = 4
            tampered['rejected_hash'] = orig_hash
            p.write(rej_path, tampered)
            with patch.object(p, 'bundle_for', return_value=b), patch('vendor.gemini.GeminiClient', return_value=client):
                with self.assertRaises(ValueError) as cm:
                    p.assess(args)
                self.assertIn('rejected_hash mismatch', str(cm.exception))

            # 4. Missing model or model_settings must fail
            no_model = make_valid_payload()
            del no_model['record']['model']
            no_model['record']['record_hash'] = p.digest({k: v for k, v in no_model['record'].items() if k != 'record_hash'})
            no_model['rejected_hash'] = p.digest({k: v for k, v in no_model.items() if k != 'rejected_hash'})
            p.write(rej_path, no_model)
            with patch.object(p, 'bundle_for', return_value=b), patch('vendor.gemini.GeminiClient', return_value=client):
                with self.assertRaises(ValueError) as cm:
                    p.assess(args)
                self.assertIn('model missing or differs', str(cm.exception))

            # 5. Duplicate subgroup assessments must fail
            dup_sgs = make_valid_payload()
            dup_sgs['record']['response']['assessments'] = [
                {'subgroup': sg5[0], 'score': 0},
                {'subgroup': sg5[0], 'score': 0},
                {'subgroup': sg5[2], 'score': 0},
                {'subgroup': sg5[3], 'score': 0},
                {'subgroup': sg5[4], 'score': 0},
            ]
            dup_sgs['record']['record_hash'] = p.digest({k: v for k, v in dup_sgs['record'].items() if k != 'record_hash'})
            dup_sgs['rejected_hash'] = p.digest({k: v for k, v in dup_sgs.items() if k != 'rejected_hash'})
            p.write(rej_path, dup_sgs)
            with patch.object(p, 'bundle_for', return_value=b), patch('vendor.gemini.GeminiClient', return_value=client):
                with self.assertRaises(ValueError) as cm:
                    p.assess(args)
                self.assertIn('duplicate, missing, or unexpected', str(cm.exception))

            # 6. Unrelated version through declared original_execution_seal without explicit import provenance must fail
            foreign_ver = make_valid_payload()
            foreign_ver['record']['version'] = 'b' * 64
            foreign_ver['record']['original_execution_seal'] = 'b' * 64
            foreign_ver['record']['record_hash'] = p.digest({k: v for k, v in foreign_ver['record'].items() if k != 'record_hash'})
            foreign_ver['rejected_hash'] = p.digest({k: v for k, v in foreign_ver.items() if k != 'rejected_hash'})
            p.write(rej_path, foreign_ver)
            with patch.object(p, 'bundle_for', return_value=b), patch('vendor.gemini.GeminiClient', return_value=client):
                with self.assertRaises(ValueError) as cm:
                    p.assess(args)
                self.assertIn('version mismatch', str(cm.exception))

            # 7. Valid rejected payload passes verification and skips batch 1 (variant 0), proceeding to batch 2 (variant 5)
            valid = make_valid_payload()
            p.write(rej_path, valid)
            client.reset_mock()
            def gen(pin, system, parts, **kwargs):
                return {'assessments': []}
            client.generate_json.side_effect = gen
            with patch.object(p, 'bundle_for', return_value=b), patch('vendor.gemini.GeminiClient', return_value=client):
                try:
                    p.assess(args)
                except Exception:
                    pass
            self.assertEqual(client.generate_json.call_count, 1)
            self.assertEqual(client.generate_json.call_args[1]['variant'], 5)

    def test_rebuilding_manifest_preserves_historical_origin_synthetic(self):
        """Standalone regression: Rebuilding provenance manifest with synthetic fixture binds historical origin to request-cache identity."""
        import build_provenance_manifest as bpm
        from types import SimpleNamespace

        hist_ver = "946a8543adc9b28c4195d4544727636b89f108966029a57c8b079ea5d2eb9fe5"
        target_ver = "9faf00f6d14bc325c28d7e84be515944b3034635fb17a98be0f9e785b489f3f0"

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "work"
            work.mkdir()
            (work / "cache" / "raw").mkdir(parents=True)
            res_dir = work / "versions" / target_ver / "results" / "baseline"
            res_dir.mkdir(parents=True)
            (work / "versions" / hist_ver / "results").mkdir(parents=True)

            plan = {"studies": [{"study_id": "S54", "split": "holdout", "building_scope": "yes", "family_id": "FAM_S54", "pdf": "54.pdf"}]}
            p.write(work / "plan.json", plan)
            p.write(work / "documents.json", {"54.pdf": {"path": "papers/54.pdf", "sha256": "0" * 64}})

            subgroups = {f"SG{i:02d}": f"Requirement {i}" for i in range(1, 26)}
            bundle_data = {
                "seal": target_ver,
                "authority": {"rubric_verbatim": "Table 4: Verbatim rubric", "subgroups": subgroups, "sources": {}},
                "plan": plan,
                "documents": {"54.pdf": {"path": "papers/54.pdf", "sha256": "0" * 64, "pages": [{"page": 1, "text": "Sample page"}]}},
                "code": {},
                "runtime": {}
            }
            p.write(work / "versions" / target_ver / "bundle.json", bundle_data)
            p.write(work / "versions" / hist_ver / "bundle.json", bundle_data)

            ck = "fdc71772c4a1d2b0792f3ce1365bbf488ca1391ad5550ba17ea173c385268520"
            assessments = [{"subgroup": f"SG{i:02d}", "score": 0, "evidence": [{"page": 1, "quote": "Sample text", "role": "background"}]} for i in range(16, 21)]
            resp_obj = {"assessments": assessments}
            raw_data = {
                "candidates": [{"content": {"parts": [{"text": json.dumps(resp_obj)}]}}],
                "usage_metadata": {"prompt_token_count": 15000, "candidates_token_count": 500, "thoughts_token_count": 2000},
                "create_time": "2026-11-08T01:07:04Z",
                "model_version": "gemini-3.8-flash"
            }
            p.write(work / "cache" / "raw" / f"{ck}_test.json", raw_data)
            p.write(work / "cache" / f"{ck}.json", {"label": "flash/S54/15", "model": "gemini-3.8-flash", "temperature": 0.0})

            ph = p.digest(p.prompt_for(bundle_data, plan["studies"][0], "baseline", {f"SG{i:02d}": f"Requirement {i}" for i in range(16, 21)}))
            rec = {
                "version": target_ver,
                "stage": "baseline",
                "study_id": "S54",
                "batch_index": 4,
                "model": "gemini-3.8-flash",
                "model_settings": p.model_config("baseline"),
                "prompt_hash": ph,
                "response": resp_obj,
                "record_hash": "dummy_hash",
            }
            p.write(res_dir / "S54_4.rejected.json", {"rejected_hash": p.digest(rec), "validation_error": "test err", "record": rec})

            tmp_out = root / "test_manifest.json"
            args = SimpleNamespace(work_dir=work, historical_version=hist_ver, target_version=target_ver, output=tmp_out)
            with patch("sys.argv", ["build_provenance_manifest.py"]):
                with patch("argparse.ArgumentParser.parse_args", return_value=args):
                    bpm.main()

            self.assertTrue(tmp_out.exists())
            manifest = json.loads(tmp_out.read_text(encoding="utf-8"))
            s54_entries = [
                b for b in manifest.get("batches", [])
                if b.get("study_id") == "S54" and b.get("stage") == "baseline" and b.get("batch_index") == 4
            ]
            self.assertEqual(len(s54_entries), 1)
            s54_4 = s54_entries[0]
            self.assertEqual(
                s54_4["original_execution_seal"],
                "665aa76ed68e8c69c9c58616bd7f119628ec7438ec02c0a8d2681852a6eb3a8a",
                "baseline/S54_4 original_execution_seal must be 665aa76e..., not 946a..."
            )
            self.assertEqual(
                s54_4["request_cache_key"],
                ck
            )

    @unittest.skipUnless((Path(__file__).resolve().parent / "work" / "plan.json").exists(), "Integration test requires private work directory")
    def test_rebuilding_manifest_preserves_s54_baseline_origin_integration(self):
        """Integration test: Rebuilding provenance manifest on real corpus permanently preserves baseline/S54_4 origin."""
        import build_provenance_manifest as bpm
        from types import SimpleNamespace

        hist_ver = "946a8543adc9b28c4195d4544727636b89f108966029a57c8b079ea5d2eb9fe5"
        target_ver = "9faf00f6d14bc325c28d7e84be515944b3034635fb17a98be0f9e785b489f3f0"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_out = Path(tmpdir) / "test_manifest.json"
            args = SimpleNamespace(
                work_dir=Path(__file__).resolve().parent / "work",
                historical_version=hist_ver,
                target_version=target_ver,
                output=tmp_out
            )
            with patch("sys.argv", ["build_provenance_manifest.py"]):
                with patch("argparse.ArgumentParser.parse_args", return_value=args):
                    bpm.main()

            self.assertTrue(tmp_out.exists())
            manifest = json.loads(tmp_out.read_text(encoding="utf-8"))
            s54_entries = [
                b for b in manifest.get("batches", [])
                if b.get("study_id") == "S54" and b.get("stage") == "baseline" and b.get("batch_index") == 4
            ]
            self.assertEqual(len(s54_entries), 1)
            s54_4 = s54_entries[0]
            self.assertEqual(
                s54_4["original_execution_seal"],
                "665aa76ed68e8c69c9c58616bd7f119628ec7438ec02c0a8d2681852a6eb3a8a",
                "baseline/S54_4 original_execution_seal must be 665aa76e..., not 946a..."
            )
            self.assertEqual(
                s54_4["request_cache_key"],
                "fdc71772c4a1d2b0792f3ce1365bbf488ca1391ad5550ba17ea173c385268520"
            )


if __name__ == '__main__':
    unittest.main()
