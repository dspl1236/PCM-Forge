"""Tests for the PCM 3.1 activation-code generator CLI."""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generate_codes as gc

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP = os.path.join(REPO_ROOT, 'docs', 'index.html')


def webapp_features():
    """The featuresFor() table from the web app, the parity reference."""
    html = open(WEBAPP, encoding='utf-8').read()
    body = html.split('function featuresFor(')[1].split('\n}')[0]
    found = re.findall(r"\{name:'([^']+)',\s*hex:(?:'([^']*)'|(flHex)),\s*desc:'([^']*)'", body)
    return [(name, hex_lit or 'FEATURELEVEL', desc) for name, hex_lit, _fl, desc in found]


class TestFeatureTable:
    def test_includes_tel_telephone_module(self):
        names = [f[0] for f in gc.features_for(0x0003)]
        assert 'TEL' in names

    def test_feature_names_match_the_web_app(self):
        assert [f[0] for f in gc.features_for(0x0003)] == [f[0] for f in webapp_features()]

    def test_feature_descriptions_match_the_web_app(self):
        ours = {f[0]: f[4] for f in gc.features_for(0x0003)}
        theirs = {name: desc for name, _hex, desc in webapp_features()}
        assert ours == theirs

    def test_feature_hex_values_match_the_web_app(self):
        ours = {f[0]: f[1] for f in gc.features_for(0x0003) if f[0] != 'FeatureLevel'}
        theirs = {n: h for n, h, _d in webapp_features() if n != 'FeatureLevel'}
        assert ours == theirs

    def test_swids_are_unique_so_add_remove_can_key_on_them(self):
        swids = [f[2] for f in gc.features_for(0x0003)]
        assert len(swids) == len(set(swids))


def webapp_const(name):
    """Decode one of the web app's ksh script string constants."""
    html = open(WEBAPP, encoding='utf-8').read()
    m = re.search(rf"const {name}\s*=\s*'((?:[^'\\]|\\.)*)'\s*;", html)
    assert m, f'{name} not found in web app'
    return m.group(1).encode('utf-8').decode('unicode_escape')


class TestXorCipher:
    """Cipher must match proc_scriptlauncher (research/DISCOVERY_NARRATIVE.md:229)."""

    def test_matches_the_documented_reference_implementation(self):
        seed = 0x001be3ac

        def ref(data):
            nonlocal seed
            seed = 0x001be3ac

            def rand():
                nonlocal seed
                r0 = seed & 0xFFFFFFFF
                r1 = ((seed >> 1) | (seed << 31)) & 0xFFFFFFFF
                r3 = (((r1 >> 16) & 0xFF) + r1) & 0xFFFFFFFF
                r1 = (((r3 >> 8) & 0xFF) << 16) & 0xFFFFFFFF
                seed = (r3 - r1) & 0xFFFFFFFF
                return r0

            rand()
            return bytes(b ^ (rand() & 0xFF) for b in data)

        payload = gc.BOOTSTRAP.encode('utf-8')
        assert gc.xor_encode(payload) == ref(payload)

    def test_is_its_own_inverse_so_the_pcm_can_decode_it(self):
        payload = b'#!/bin/ksh\necho hello\n'
        assert gc.xor_encode(gc.xor_encode(payload)) == payload

    def test_actually_transforms_the_payload(self):
        payload = gc.BOOTSTRAP.encode('utf-8')
        assert gc.xor_encode(payload) != payload


class TestScriptConstants:
    def test_bootstrap_matches_the_web_app(self):
        assert gc.BOOTSTRAP == webapp_const('BOOTSTRAP')

    def test_run_activate_matches_the_web_app(self):
        assert gc.RUN_ACTIVATE == webapp_const('RUN_ACTIVATE')

    def test_run_diag_matches_the_web_app(self):
        assert gc.RUN_DIAG == webapp_const('RUN_DIAG')

    def test_run_activate_rotates_the_existing_activation_file(self):
        assert 'PagSWAct.002.bak' in gc.RUN_ACTIVATE

    def test_run_activate_shows_the_status_splash(self):
        assert 'forge_splash' in gc.RUN_ACTIVATE

    def test_run_diag_does_not_write_activations(self):
        assert 'cp "${USBROOT}/PagSWAct.002" /HBpersistence' not in gc.RUN_DIAG


VIN = 'WP1ZZZ92ZFLA12345'


class TestUsbWrite:
    def test_writes_the_three_file_structure(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        for name in ('copie_scr.sh', 'run.sh', 'PagSWAct.002'):
            assert (tmp_path / name).exists(), f'missing {name}'

    def test_bootstrap_is_xor_encoded_by_default(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        written = (tmp_path / 'copie_scr.sh').read_bytes()
        assert written == gc.xor_encode(gc.BOOTSTRAP.encode('utf-8'))
        assert not written.startswith(b'#!/bin/ksh')

    def test_no_xor_writes_plaintext_for_testing(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet', '--no-xor'])
        assert (tmp_path / 'copie_scr.sh').read_bytes() == gc.BOOTSTRAP.encode('utf-8')

    def test_run_sh_is_the_activation_script(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        assert (tmp_path / 'run.sh').read_bytes() == gc.RUN_ACTIVATE.encode('utf-8')

    def test_scripts_use_lf_endings_qnx_ksh_rejects_crlf(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet', '--no-xor'])
        for name in ('copie_scr.sh', 'run.sh'):
            assert b'\r\n' not in (tmp_path / name).read_bytes(), name

    def test_copies_the_splash_assets_from_the_repo(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        assert (tmp_path / 'bin' / 'forge_splash').read_bytes() == \
            open(os.path.join(REPO_ROOT, 'core', 'bin', 'forge_splash'), 'rb').read()
        for name in ('running.bin', 'done.bin'):
            assert (tmp_path / 'lib' / name).read_bytes() == \
                open(os.path.join(REPO_ROOT, 'core', 'lib', name), 'rb').read()

    def test_writes_one_28_byte_record_per_feature(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        data = (tmp_path / 'PagSWAct.002').read_bytes()
        assert len(data) == 28 * len(gc.features_for(0x0003))


def records(path):
    """Split a PagSWAct.002 into (swid, subid, code) tuples."""
    data = open(path, 'rb').read()
    out = []
    for i in range(0, len(data), 28):
        r = data[i:i + 28]
        out.append((r[18] | (r[19] << 8), r[20] | (r[21] << 8), r[:16].decode('ascii')))
    return out


class TestAddRemove:
    def test_add_appends_a_missing_feature(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        gc.main([VIN, str(tmp_path), '--quiet', '--remove', 'TEL'])
        assert 0x0102 not in [r[0] for r in records(tmp_path / 'PagSWAct.002')]
        gc.main([VIN, str(tmp_path), '--quiet', '--add', 'TEL'])
        assert 0x0102 in [r[0] for r in records(tmp_path / 'PagSWAct.002')]

    def test_add_writes_the_same_code_the_full_build_would(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        expected = dict((r[0], r[2]) for r in records(tmp_path / 'PagSWAct.002'))[0x0102]
        gc.main([VIN, str(tmp_path), '--quiet', '--remove', 'TEL'])
        gc.main([VIN, str(tmp_path), '--quiet', '--add', 'TEL'])
        got = dict((r[0], r[2]) for r in records(tmp_path / 'PagSWAct.002'))[0x0102]
        assert got == expected

    def test_add_replaces_an_existing_record_rather_than_duplicating(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        before = len(records(tmp_path / 'PagSWAct.002'))
        gc.main([VIN, str(tmp_path), '--quiet', '--add', 'TEL'])
        assert len(records(tmp_path / 'PagSWAct.002')) == before

    def test_remove_drops_only_the_named_feature(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        before = records(tmp_path / 'PagSWAct.002')
        gc.main([VIN, str(tmp_path), '--quiet', '--remove', 'KOMP'])
        after = records(tmp_path / 'PagSWAct.002')
        assert len(after) == len(before) - 1
        assert 0x0106 not in [r[0] for r in after]

    def test_add_leaves_the_other_usb_files_untouched(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        before = (tmp_path / 'copie_scr.sh').read_bytes()
        gc.main([VIN, str(tmp_path), '--quiet', '--add', 'TEL'])
        assert (tmp_path / 'copie_scr.sh').read_bytes() == before

    def test_add_without_an_existing_file_is_an_error(self, tmp_path):
        assert gc.main([VIN, str(tmp_path), '--quiet', '--add', 'TEL']) == 1

    def test_unknown_feature_name_is_an_error(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        assert gc.main([VIN, str(tmp_path), '--quiet', '--add', 'NOPE']) == 1

    def test_add_and_remove_together_is_an_error(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        with pytest.raises(SystemExit):
            gc.main([VIN, str(tmp_path), '--add', 'TEL', '--remove', 'KOMP'])

    def test_add_without_a_usb_path_is_an_error(self):
        assert gc.main([VIN, '--quiet', '--add', 'TEL']) == 1

    def test_add_with_a_vin_from_another_car_is_refused(self, tmp_path, capsys):
        """The file is signed for one car; a code for another would mix them."""
        gc.main([VIN, str(tmp_path), '--quiet'])
        assert gc.main([OTHER_VIN, str(tmp_path), '--quiet', '--add', 'SC']) == 1
        assert 'VIN' in capsys.readouterr().err

    def test_add_from_another_car_leaves_the_file_unmixed(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        before = (tmp_path / 'PagSWAct.002').read_bytes()
        gc.main([OTHER_VIN, str(tmp_path), '--quiet', '--add', 'SC'])
        assert (tmp_path / 'PagSWAct.002').read_bytes() == before
        assert gc.backup_vin_hash(
            gc.load_records(str(tmp_path / 'PagSWAct.002'))) is not None

    def test_removing_every_feature_is_refused(self, tmp_path):
        """An empty file would switch every activated feature off in the car."""
        gc.main([VIN, str(tmp_path), '--quiet'])
        all_names = ','.join(f[0] for f in gc.features_for(0x0003))
        assert gc.main([VIN, str(tmp_path), '--quiet',
                        '--remove', all_names]) == 1

    def test_refusing_the_full_removal_keeps_the_file(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        before = (tmp_path / 'PagSWAct.002').read_bytes()
        all_names = ','.join(f[0] for f in gc.features_for(0x0003))
        gc.main([VIN, str(tmp_path), '--quiet', '--remove', all_names])
        assert (tmp_path / 'PagSWAct.002').read_bytes() == before


class TestDiagnosticMode:
    def test_builds_a_stick_without_a_vin(self, tmp_path):
        assert gc.main(['--diag', str(tmp_path), '--quiet']) == 0
        assert (tmp_path / 'copie_scr.sh').exists()
        assert (tmp_path / 'run.sh').exists()

    def test_writes_the_diagnostic_script(self, tmp_path):
        gc.main(['--diag', str(tmp_path), '--quiet'])
        assert (tmp_path / 'run.sh').read_bytes() == gc.RUN_DIAG.encode('utf-8')

    def test_writes_no_activation_file(self, tmp_path):
        gc.main(['--diag', str(tmp_path), '--quiet'])
        assert not (tmp_path / 'PagSWAct.002').exists()

    def test_bootstrap_is_xor_encoded_by_default(self, tmp_path):
        gc.main(['--diag', str(tmp_path), '--quiet'])
        assert (tmp_path / 'copie_scr.sh').read_bytes() == \
            gc.xor_encode(gc.BOOTSTRAP.encode('utf-8'))

    def test_honours_no_xor(self, tmp_path):
        gc.main(['--diag', str(tmp_path), '--quiet', '--no-xor'])
        assert (tmp_path / 'copie_scr.sh').read_bytes() == gc.BOOTSTRAP.encode('utf-8')

    def test_ships_the_splash_assets(self, tmp_path):
        gc.main(['--diag', str(tmp_path), '--quiet'])
        assert (tmp_path / 'bin' / 'forge_splash').exists()

    def test_cannot_be_combined_with_add(self, tmp_path):
        with pytest.raises(SystemExit):
            gc.main(['--diag', str(tmp_path), '--add', 'TEL'])


class TestListFeatures:
    def test_lists_every_feature_name(self, capsys):
        assert gc.main(['--list-features']) == 0
        out = capsys.readouterr().out
        for name, _h, _s, _su, _d in gc.features_for(0x0003):
            assert name in out


class TestCodeListing:
    def test_header_counts_the_features_it_lists(self, capsys):
        assert gc.main([VIN]) == 0
        out = capsys.readouterr().out
        assert f"All {len(gc.features_for(0x0003))} Activation Codes" in out

    def test_default_model_label_matches_the_model_table(self, capsys):
        assert gc.main([VIN]) == 0
        label = next(desc for sub, desc in gc.MODELS.values() if sub == 0x0003)
        assert label in capsys.readouterr().out

    def test_output_is_ascii_for_legacy_consoles(self, capsys, tmp_path):
        # A cp1252 or cp437 console garbles non-ASCII punctuation.
        assert gc.main([VIN]) == 0
        assert gc.main([VIN, str(tmp_path)]) == 0
        assert gc.main([VIN, str(tmp_path), '--add', 'TEL']) == 0
        out = capsys.readouterr().out
        assert out.isascii(), [c for c in out if not c.isascii()]


class TestVinToNumber:
    """The firmware works on ASCII bytes; Python's Unicode-aware character
    tests must not make us diverge from it (or from the web app)."""

    def test_unicode_digit_does_not_crash(self):
        # Python's str.isdigit() is true for U+00B2, but int() rejects it.
        gc.vin_to_number('WP1ZZZ92ZFLA1234²')

    def test_non_ascii_counts_as_zero_like_the_firmware(self):
        assert gc.vin_to_number('WP1ZZZ92ZFLA1234²') == \
               gc.vin_to_number('WP1ZZZ92ZFLA1234-')

    def test_umlaut_counts_as_zero_like_the_firmware(self):
        assert gc.vin_to_number('WP1ZZZ92ZFLA1234ä') == \
               gc.vin_to_number('WP1ZZZ92ZFLA1234-')

    def test_ascii_letters_and_digits_are_unaffected(self):
        # value cross-checked against the web app's vinToNumber()
        assert gc.vin_to_number('WP1ZZZ92ZFLA12345') == 368890


FACTORY_CSV = os.path.join(REPO_ROOT, 'research', 'firmware', 'PagSWAct.csv')

# Cells that are corrupt in the source CSV, not algorithm mismatches:
# the NavDB cells duplicate a neighbouring column verbatim, SE0801's BTH
# duplicates its ENGINEERING code, and its KOMP holds 17 hex digits -- more
# than a code can carry, since every code is < N (63 bits).
CORRUPT_CELLS = {
    ('SEB201', 'NavDBArgentina'), ('SEB202', 'NavDBArgentina'),
    ('SEB207', 'NavDBArgentina'), ('SEB201', 'NavDBChina'),
    ('SEB202', 'NavDBChina'), ('SEB207', 'NavDBChina'),
    ('SE0801', 'BTH'), ('SE0801', 'KOMP'),
}


def factory_rows():
    """Genuine Porsche activation records recovered from the firmware."""
    lines = [l for l in open(FACTORY_CSV, encoding='utf-8') if l.strip()]
    cols = [h.split(':', 1)[1].strip() if ':' in h else h.strip()
            for h in [x.strip() for x in lines[0].lstrip('/').split(';')]]
    rows = [dict(zip(cols, [v.strip() for v in l.split(';')])) for l in lines[1:]]
    feature_cols = [c for c in cols[3:] if c and c != 'FeatureLevel']
    return rows, feature_cols


def factory_cells():
    """Yield (row_name, vin, feature, code) for every usable factory code."""
    rows, feature_cols = factory_rows()
    for r in rows:
        for name in feature_cols:
            code = r.get(name, '')
            if code in ('', '0') or (r['Name'], name) in CORRUPT_CELLS:
                continue
            yield r['Name'], r['VIN'], name, code


class TestAgainstFactoryCodes:
    """Ground truth: real activation codes extracted from PCM 3.1 firmware."""

    def test_the_csv_still_provides_a_meaningful_sample(self):
        assert len(list(factory_cells())) > 450

    def test_every_factory_code_decrypts_to_its_feature_and_vin(self):
        """The PCM verifies by RSA-decrypting with the public exponent E.
        Doing the same must recover the feature's SWID and the VIN hash."""
        swids = {f[0]: f[2] for f in gc.features_for(0x0003)}
        bad = []
        for row, vin, name, code in factory_cells():
            plain = f"{pow(int(code, 16), gc.E, gc.N):016x}"
            feature_half, vin_half = plain[0::2], plain[1::2]
            if (int(feature_half[:4], 16) != swids[name]
                    or vin_half != f"{gc.vin_to_number(vin):08x}"):
                bad.append(f'{row}/{name}')
        assert not bad, f'did not decrypt correctly: {bad}'

    def test_we_reproduce_factory_codes_for_the_documented_subids(self):
        """Where the factory used the SubID our table carries, the generated
        code must match the factory's byte for byte."""
        feats = {f[0]: (f[1], f[3]) for f in gc.features_for(0x0003)}
        checked = 0
        for row, vin, name, code in factory_cells():
            feat_hex, our_subid = feats[name]
            plain = f"{pow(int(code, 16), gc.E, gc.N):016x}"
            if int(plain[0::2][4:], 16) != our_subid:
                continue  # a different variant of this feature, not our default
            assert int(gc.generate_code(vin, feat_hex), 16) == int(code, 16), \
                f'{row}/{name}'
            checked += 1
        assert checked > 400, f'only {checked} codes exercised'

    def test_no_factory_code_exceeds_the_modulus(self):
        for row, _vin, name, code in factory_cells():
            assert int(code, 16) < gc.N, f'{row}/{name}'


class TestFileRoundTrip:
    """Write a stick, then read it back the way the PCM would."""

    def test_every_written_record_decrypts_to_its_feature_and_vin(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet', '--model', 'cayenne-se'])
        data = (tmp_path / 'PagSWAct.002').read_bytes()
        expected_vin_half = f'{gc.vin_to_number(VIN):08x}'
        by_swid = {f[2]: f for f in gc.features_for(0x0043)}
        assert len(data) % 28 == 0
        for i in range(0, len(data), 28):
            rec = data[i:i + 28]
            code = rec[:16].decode('ascii')
            swid = rec[18] | (rec[19] << 8)
            subid = rec[20] | (rec[21] << 8)
            plain = f'{pow(int(code, 16), gc.E, gc.N):016x}'
            feature_half, vin_half = plain[0::2], plain[1::2]
            assert int(feature_half[:4], 16) == swid, f'swid mismatch at {i}'
            assert int(feature_half[4:], 16) == subid, f'subid mismatch at {i}'
            assert vin_half == expected_vin_half, f'vin mismatch at {i}'
            assert swid in by_swid, f'unknown swid 0x{swid:04x}'

    def test_written_records_carry_the_active_flags(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        data = (tmp_path / 'PagSWAct.002').read_bytes()
        for i in range(0, len(data), 28):
            assert data[i + 22] == 1, f'record {i // 28} not marked active'
            assert data[i + 24] == 1, f'record {i // 28} missing trailing flag'

    def test_add_produces_a_byte_identical_record_to_the_full_build(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        full = (tmp_path / 'PagSWAct.002').read_bytes()
        original = {full[i + 18] | (full[i + 19] << 8): full[i:i + 28]
                    for i in range(0, len(full), 28)}
        gc.main([VIN, str(tmp_path), '--quiet', '--remove', 'TEL'])
        gc.main([VIN, str(tmp_path), '--quiet', '--add', 'TEL'])
        rebuilt = (tmp_path / 'PagSWAct.002').read_bytes()
        readded = {rebuilt[i + 18] | (rebuilt[i + 19] << 8): rebuilt[i:i + 28]
                   for i in range(0, len(rebuilt), 28)}[0x0102]
        assert readded == original[0x0102]

    def test_featurelevel_record_carries_the_selected_model(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet', '--model', 'cayenne-se'])
        data = (tmp_path / 'PagSWAct.002').read_bytes()
        for i in range(0, len(data), 28):
            if (data[i + 18] | (data[i + 19] << 8)) == 0x010e:
                assert (data[i + 20] | (data[i + 21] << 8)) == 0x0043
                return
        pytest.fail('no FeatureLevel record written')

    def test_bootstrap_survives_the_pcm_decoder(self, tmp_path):
        """proc_scriptlauncher XOR-decodes copie_scr.sh; that must yield ksh."""
        gc.main([VIN, str(tmp_path), '--quiet'])
        on_stick = (tmp_path / 'copie_scr.sh').read_bytes()

        def pcm_decode(data):  # independent reimplementation of the launcher
            seed = 0x001be3ac
            out = bytearray()
            def rnd():
                nonlocal seed
                r0 = seed
                r1 = ((seed >> 1) | (seed << 31)) & 0xFFFFFFFF
                r3 = (((r1 >> 16) & 0xFF) + r1) & 0xFFFFFFFF
                r1 = (((r3 >> 8) & 0xFF) << 16) & 0xFFFFFFFF
                seed = (r3 - r1) & 0xFFFFFFFF
                return r0
            rnd()
            for b in data:
                out.append(b ^ (rnd() & 0xFF))
            return bytes(out)

        decoded = pcm_decode(on_stick).decode('utf-8')
        assert decoded.startswith('#!/bin/ksh')
        assert './run.sh' in decoded
        assert decoded == gc.BOOTSTRAP


class TestSubIdOverride:
    """--subid NAME=VALUE selects a non-default variant of a feature.
    Defaults stay as they are: every one is the most common value in the
    factory data (research/firmware/PagSWAct.csv)."""

    def test_default_is_unchanged_without_the_flag(self):
        assert {f[0]: f[3] for f in gc.features_for(0x0003)}['NavDBEurope'] == 0x00ff

    def test_override_changes_the_feature_hex(self):
        feats = gc.features_for(0x0003, subid_overrides={'NavDBEurope': 0x0001})
        entry = next(f for f in feats if f[0] == 'NavDBEurope')
        assert entry[1] == '20010001' and entry[3] == 0x0001

    def test_override_leaves_other_features_alone(self):
        base = gc.features_for(0x0003)
        over = gc.features_for(0x0003, subid_overrides={'NavDBEurope': 0x0001})
        changed = [b[0] for b, o in zip(base, over) if b != o]
        assert changed == ['NavDBEurope']

    def test_override_is_case_insensitive_on_the_name(self):
        feats = gc.features_for(0x0003, subid_overrides={'navdbeurope': 0x0001})
        assert next(f for f in feats if f[0] == 'NavDBEurope')[3] == 0x0001

    def test_cli_override_reaches_the_written_record(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet', '--subid', 'NavDBEurope=0x0001'])
        data = (tmp_path / 'PagSWAct.002').read_bytes()
        rec = next(data[i:i + 28] for i in range(0, len(data), 28)
                   if (data[i + 18] | (data[i + 19] << 8)) == 0x2001)
        assert (rec[20] | (rec[21] << 8)) == 0x0001

    def test_overridden_record_still_decrypts_consistently(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet', '--subid', 'TVINF=0x0109'])
        data = (tmp_path / 'PagSWAct.002').read_bytes()
        rec = next(data[i:i + 28] for i in range(0, len(data), 28)
                   if (data[i + 18] | (data[i + 19] << 8)) == 0x0107)
        plain = f'{pow(int(rec[:16].decode("ascii"), 16), gc.E, gc.N):016x}'
        assert int(plain[0::2][4:], 16) == 0x0109 == (rec[20] | (rec[21] << 8))

    def test_reproduces_a_real_factory_variant_code(self):
        """CanLog_Idx1 (WP0ZZZ97Z8L040010) carries NavDBEurope at index 1."""
        feats = gc.features_for(0x0003, subid_overrides={'NavDBEurope': 0x0001})
        entry = next(f for f in feats if f[0] == 'NavDBEurope')
        code = gc.generate_code('WP0ZZZ97Z8L040010', entry[1])
        assert int(code, 16) == int('4f78a43e5516c49a', 16)

    def test_override_applies_to_add(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        gc.main([VIN, str(tmp_path), '--quiet', '--add', 'NavDBEurope',
                 '--subid', 'NavDBEurope=0x0001'])
        data = (tmp_path / 'PagSWAct.002').read_bytes()
        rec = next(data[i:i + 28] for i in range(0, len(data), 28)
                   if (data[i + 18] | (data[i + 19] << 8)) == 0x2001)
        assert (rec[20] | (rec[21] << 8)) == 0x0001

    def test_multiple_overrides_at_once(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet',
                 '--subid', 'SSS=0x0001', '--subid', 'OnlineServices=0x0000'])
        data = (tmp_path / 'PagSWAct.002').read_bytes()
        got = {data[i + 18] | (data[i + 19] << 8): data[i + 20] | (data[i + 21] << 8)
               for i in range(0, len(data), 28)}
        assert got[0x0104] == 0x0001 and got[0x0111] == 0x0000

    def test_unknown_feature_is_an_error(self, tmp_path):
        assert gc.main([VIN, str(tmp_path), '--quiet', '--subid', 'NOPE=0x0001']) == 1

    def test_malformed_value_is_an_error(self, tmp_path):
        assert gc.main([VIN, str(tmp_path), '--quiet', '--subid', 'SSS=xyz']) == 1

    def test_missing_equals_sign_is_an_error(self, tmp_path):
        assert gc.main([VIN, str(tmp_path), '--quiet', '--subid', 'SSS']) == 1

    def test_out_of_range_value_is_an_error(self, tmp_path):
        assert gc.main([VIN, str(tmp_path), '--quiet', '--subid', 'SSS=0x10000']) == 1


class TestShow:
    """--show decodes an existing PagSWAct.002 the way the PCM reads it."""

    def test_lists_every_feature_in_the_file(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet'])
        assert gc.main(['--show', str(tmp_path / 'PagSWAct.002')]) == 0
        out = capsys.readouterr().out
        for name, _h, _s, _su, _d in gc.features_for(0x0003):
            assert name in out, name

    def test_accepts_a_directory_and_finds_the_file(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet'])
        assert gc.main(['--show', str(tmp_path)]) == 0
        assert 'ENGINEERING' in capsys.readouterr().out

    def test_reports_the_vin_hash_the_codes_were_signed_for(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet'])
        gc.main(['--show', str(tmp_path)])
        assert f'{gc.vin_to_number(VIN):08x}' in capsys.readouterr().out

    def test_confirms_a_matching_vin(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet'])
        assert gc.main([VIN, '--show', str(tmp_path)]) == 0
        assert 'MATCH' in capsys.readouterr().out.upper()

    def test_flags_a_vin_that_does_not_belong_to_the_file(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet'])
        gc.main(['WP0ZZZ97Z8L040010', '--show', str(tmp_path)])
        assert 'MISMATCH' in capsys.readouterr().out.upper()

    def test_marks_a_non_default_subid_variant(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet', '--subid', 'NavDBEurope=0x0001'])
        capsys.readouterr()  # discard the build output; only --show matters here
        gc.main(['--show', str(tmp_path)])
        out = [l for l in capsys.readouterr().out.splitlines() if 'NavDBEurope' in l]
        # A map database's SubID is its map level (generate_codes.map_level).
        assert out and 'map level 1' in out[0].lower(), out

    def test_reports_an_unknown_swid_rather_than_hiding_it(self, tmp_path, capsys):
        rec = bytearray(gc.build_record(VIN, '09990000', 0x0999, 0x0000))
        (tmp_path / 'PagSWAct.002').write_bytes(bytes(rec))
        assert gc.main(['--show', str(tmp_path)]) == 0
        assert '0x0999' in capsys.readouterr().out

    def test_flags_a_record_whose_code_does_not_verify(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet'])
        data = bytearray((tmp_path / 'PagSWAct.002').read_bytes())
        data[0] = ord('0') if data[0] != ord('0') else ord('1')  # corrupt one code
        (tmp_path / 'PagSWAct.002').write_bytes(bytes(data))
        gc.main(['--show', str(tmp_path)])
        assert '!' in capsys.readouterr().out

    def test_missing_file_is_an_error(self, tmp_path):
        assert gc.main(['--show', str(tmp_path / 'nothing.002')]) == 1

    def test_malformed_file_is_an_error(self, tmp_path):
        (tmp_path / 'PagSWAct.002').write_bytes(b'\x00' * 27)
        assert gc.main(['--show', str(tmp_path)]) == 1

    def test_cannot_be_combined_with_add(self, tmp_path):
        with pytest.raises(SystemExit):
            gc.main(['--show', str(tmp_path), '--add', 'TEL'])


class TestShowWildcardSubId:
    """A record header may carry SubID 0xffff as a wildcard. Real factory data
    pulled off a car (Navigation/UMS/BTH) signs SubID 0x0000 but stores 0xffff
    in the header -- that is valid, not a corrupt record."""

    def _factory_like(self, tmp_path, header_subid):
        rec = bytearray(gc.build_record(VIN, '01010000', 0x0101, 0x0000))
        rec[20] = header_subid & 0xFF
        rec[21] = (header_subid >> 8) & 0xFF
        (tmp_path / 'PagSWAct.002').write_bytes(bytes(rec))

    def test_wildcard_header_is_not_reported_as_corrupt(self, tmp_path, capsys):
        self._factory_like(tmp_path, 0xffff)
        gc.main(['--show', str(tmp_path)])
        assert 'does not match' not in capsys.readouterr().out

    def test_wildcard_header_is_labelled_as_such(self, tmp_path, capsys):
        self._factory_like(tmp_path, 0xffff)
        gc.main(['--show', str(tmp_path)])
        # Check the feature's own row, not the whole output: pytest names the
        # tmp_path after this test, so the path itself contains "wildcard".
        row = next(l for l in capsys.readouterr().out.splitlines()
                   if l.strip().startswith('Navigation'))
        assert 'wildcard' in row.lower(), row

    def test_wildcard_still_reports_the_vin_hash(self, tmp_path, capsys):
        self._factory_like(tmp_path, 0xffff)
        gc.main(['--show', str(tmp_path)])
        assert f'{gc.vin_to_number(VIN):08x}' in capsys.readouterr().out

    def test_a_genuinely_wrong_subid_is_still_reported(self, tmp_path, capsys):
        self._factory_like(tmp_path, 0x1234)
        gc.main(['--show', str(tmp_path)])
        assert 'does not match' in capsys.readouterr().out


class TestShowFindsBackupFiles:
    """A diagnostic stick holds PagSWAct_backup_<stamp>.002, not PagSWAct.002 --
    pointing --show at the stick must still work."""

    def _write(self, path, name):
        path.mkdir(exist_ok=True)
        (path / name).write_bytes(bytes(gc.build_record(VIN, '01010000', 0x0101, 0)))

    def test_finds_a_backup_when_there_is_no_canonical_file(self, tmp_path, capsys):
        self._write(tmp_path, 'PagSWAct_backup_nodate.002')
        assert gc.main(['--show', str(tmp_path)]) == 0
        assert 'Navigation' in capsys.readouterr().out

    def test_names_the_file_it_picked(self, tmp_path, capsys):
        self._write(tmp_path, 'PagSWAct_backup_nodate.002')
        gc.main(['--show', str(tmp_path)])
        assert 'PagSWAct_backup_nodate.002' in capsys.readouterr().out

    def test_prefers_the_canonical_file_when_both_exist(self, tmp_path, capsys):
        self._write(tmp_path, 'PagSWAct_backup_nodate.002')
        self._write(tmp_path, 'PagSWAct.002')
        gc.main(['--show', str(tmp_path)])
        out = capsys.readouterr().out
        assert 'PagSWAct.002' in out and 'backup' not in out

    def test_several_backups_are_listed_instead_of_guessing(self, tmp_path, capsys):
        self._write(tmp_path, 'PagSWAct_backup_20250101_120000.002')
        self._write(tmp_path, 'PagSWAct_backup_20250202_120000.002')
        assert gc.main(['--show', str(tmp_path)]) == 1
        err = capsys.readouterr().err
        assert '20250101_120000' in err and '20250202_120000' in err

    def test_empty_directory_names_both_patterns(self, tmp_path, capsys):
        tmp_path.mkdir(exist_ok=True)
        assert gc.main(['--show', str(tmp_path)]) == 1
        err = capsys.readouterr().err
        assert 'PagSWAct.002' in err and 'PagSWAct_backup' in err

    def test_an_explicit_file_path_still_works(self, tmp_path, capsys):
        self._write(tmp_path, 'PagSWAct_backup_nodate.002')
        assert gc.main(['--show', str(tmp_path / 'PagSWAct_backup_nodate.002')]) == 0
        assert 'Navigation' in capsys.readouterr().out


class TestAddRemoveMultiple:
    """--add/--remove take several features: comma-separated and repeatable."""

    def _swids(self, tmp_path):
        return [r[0] for r in records(tmp_path / 'PagSWAct.002')]

    def test_comma_separated_add(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        gc.main([VIN, str(tmp_path), '--quiet', '--remove', 'TEL,KOMP'])
        assert 0x0102 not in self._swids(tmp_path)
        gc.main([VIN, str(tmp_path), '--quiet', '--add', 'TEL,KOMP'])
        got = self._swids(tmp_path)
        assert 0x0102 in got and 0x0106 in got

    def test_comma_separated_remove(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        before = len(self._swids(tmp_path))
        gc.main([VIN, str(tmp_path), '--quiet', '--remove', 'TEL,KOMP,SDARS'])
        got = self._swids(tmp_path)
        assert len(got) == before - 3
        assert not {0x0102, 0x0106, 0x0108} & set(got)

    def test_repeating_the_flag_also_works(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        gc.main([VIN, str(tmp_path), '--quiet', '--remove', 'TEL', '--remove', 'KOMP'])
        got = self._swids(tmp_path)
        assert 0x0102 not in got and 0x0106 not in got

    def test_whitespace_around_names_is_tolerated(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        gc.main([VIN, str(tmp_path), '--quiet', '--remove', ' TEL , KOMP '])
        got = self._swids(tmp_path)
        assert 0x0102 not in got and 0x0106 not in got

    def test_added_codes_match_the_full_build(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        want = {r[0]: r[2] for r in records(tmp_path / 'PagSWAct.002')}
        gc.main([VIN, str(tmp_path), '--quiet', '--remove', 'TEL,KOMP'])
        gc.main([VIN, str(tmp_path), '--quiet', '--add', 'TEL,KOMP'])
        got = {r[0]: r[2] for r in records(tmp_path / 'PagSWAct.002')}
        assert got[0x0102] == want[0x0102] and got[0x0106] == want[0x0106]

    def test_one_bad_name_rejects_the_whole_call(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        before = self._swids(tmp_path)
        assert gc.main([VIN, str(tmp_path), '--quiet', '--remove', 'TEL,NOPE']) == 1
        assert self._swids(tmp_path) == before, 'file must stay untouched on error'

    def test_the_bad_name_is_named_in_the_error(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet'])
        gc.main([VIN, str(tmp_path), '--quiet', '--add', 'TEL,NOPE'])
        assert 'NOPE' in capsys.readouterr().err

    def test_empty_segments_are_ignored(self, tmp_path):
        gc.main([VIN, str(tmp_path), '--quiet'])
        assert gc.main([VIN, str(tmp_path), '--quiet', '--remove', 'TEL,,KOMP']) == 0

    def test_summary_names_every_feature_touched(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet'])
        capsys.readouterr()
        gc.main([VIN, str(tmp_path), '--remove', 'TEL,KOMP'])
        out = capsys.readouterr().out
        assert 'TEL' in out and 'KOMP' in out


OTHER_VIN = 'WP0ZZZ97Z8L040010'


def make_diag_stick(tmp_path, vin=VIN, backup_name='PagSWAct_backup_nodate.002',
                    features=('Navigation', 'UMS', 'BTH')):
    """A stick as it looks after a diagnostic run: the car's own backup,
    run.sh still in diagnostic mode, plus the diagnostic leftovers."""
    gc.main(['--diag', str(tmp_path), '--quiet'])
    by_name = {f[0]: f for f in gc.features_for(0x0003)}
    data = bytearray()
    for name in features:
        _n, feat_hex, swid, subid, _d = by_name[name]
        data += gc.build_record(vin, feat_hex, swid, subid)
    (tmp_path / backup_name).write_bytes(bytes(data))
    (tmp_path / 'pcm_debug_nodate.log').write_text('diagnostic output\n')
    (tmp_path / 'pcm_ran.txt').write_text('PCM-Forge diag done\n')
    return tmp_path / backup_name


class TestFromBackup:
    def test_turns_a_diagnostic_stick_into_an_activation_stick(self, tmp_path):
        make_diag_stick(tmp_path)
        assert gc.main([str(tmp_path), '--from-backup', '--quiet']) == 0
        assert (tmp_path / 'run.sh').read_bytes() == gc.RUN_ACTIVATE.encode('utf-8')
        assert (tmp_path / 'PagSWAct.002').exists()

    def test_needs_no_vin_when_nothing_is_added(self, tmp_path):
        make_diag_stick(tmp_path)
        assert gc.main([str(tmp_path), '--from-backup', '--quiet']) == 0

    def test_carries_the_backup_records_over_unchanged(self, tmp_path):
        backup = make_diag_stick(tmp_path)
        gc.main([str(tmp_path), '--from-backup', '--quiet'])
        assert (tmp_path / 'PagSWAct.002').read_bytes() == backup.read_bytes()

    def test_leaves_the_backup_and_the_logs_alone(self, tmp_path):
        backup = make_diag_stick(tmp_path)
        before = backup.read_bytes()
        gc.main([str(tmp_path), '--from-backup', '--quiet'])
        assert backup.read_bytes() == before
        assert (tmp_path / 'pcm_debug_nodate.log').exists()

    def test_ships_the_bootstrap_and_splash_assets(self, tmp_path):
        make_diag_stick(tmp_path)
        gc.main([str(tmp_path), '--from-backup', '--quiet'])
        assert (tmp_path / 'copie_scr.sh').read_bytes() == \
            gc.xor_encode(gc.BOOTSTRAP.encode('utf-8'))
        assert (tmp_path / 'bin' / 'forge_splash').exists()

    def test_adds_a_feature_on_top_of_the_backup(self, tmp_path):
        make_diag_stick(tmp_path)
        assert gc.main([VIN, str(tmp_path), '--from-backup',
                        '--add', 'SDARS', '--quiet']) == 0
        swids = [r[0] for r in records(tmp_path / 'PagSWAct.002')]
        assert 0x0108 in swids and 0x0101 in swids, swids

    def test_removes_a_feature_from_the_backup(self, tmp_path):
        make_diag_stick(tmp_path)
        gc.main([VIN, str(tmp_path), '--from-backup', '--remove', 'UMS', '--quiet'])
        swids = [r[0] for r in records(tmp_path / 'PagSWAct.002')]
        assert 0x0109 not in swids and 0x0101 in swids

    def test_adding_without_a_vin_is_an_error(self, tmp_path):
        make_diag_stick(tmp_path)
        assert gc.main([str(tmp_path), '--from-backup', '--add', 'SDARS']) == 1

    def test_a_vin_from_another_car_is_refused(self, tmp_path, capsys):
        make_diag_stick(tmp_path, vin=VIN)
        assert gc.main([OTHER_VIN, str(tmp_path), '--from-backup',
                        '--add', 'SDARS']) == 1
        assert 'VIN' in capsys.readouterr().err

    def test_a_mismatched_vin_writes_nothing(self, tmp_path):
        make_diag_stick(tmp_path)
        gc.main([OTHER_VIN, str(tmp_path), '--from-backup', '--add', 'SDARS'])
        assert not (tmp_path / 'PagSWAct.002').exists()

    def test_removing_every_backup_feature_is_refused(self, tmp_path):
        """An edit that empties the set would write a 0-byte PagSWAct.002."""
        make_diag_stick(tmp_path)  # backup holds Navigation, UMS, BTH
        assert gc.main([VIN, str(tmp_path), '--from-backup',
                        '--remove', 'Navigation,UMS,BTH', '--quiet']) == 1
        assert not (tmp_path / 'PagSWAct.002').exists()

    def test_missing_backup_is_an_error(self, tmp_path):
        gc.main(['--diag', str(tmp_path), '--quiet'])
        assert gc.main([str(tmp_path), '--from-backup']) == 1

    def test_several_backups_are_listed_instead_of_guessed(self, tmp_path, capsys):
        make_diag_stick(tmp_path, backup_name='PagSWAct_backup_20250101_000000.002')
        make_diag_stick(tmp_path, backup_name='PagSWAct_backup_20250202_000000.002')
        assert gc.main([str(tmp_path), '--from-backup']) == 1
        err = capsys.readouterr().err
        assert '20250101_000000' in err and '20250202_000000' in err

    def test_an_explicit_backup_file_resolves_the_ambiguity(self, tmp_path):
        make_diag_stick(tmp_path, backup_name='PagSWAct_backup_20250101_000000.002')
        make_diag_stick(tmp_path, backup_name='PagSWAct_backup_20250202_000000.002')
        chosen = str(tmp_path / 'PagSWAct_backup_20250202_000000.002')
        assert gc.main([str(tmp_path), '--from-backup', chosen, '--quiet']) == 0

    def test_a_bare_backup_name_is_looked_up_on_the_stick(self, tmp_path):
        """The error listing names files, so a bare name has to be accepted."""
        make_diag_stick(tmp_path, backup_name='PagSWAct_backup_20250101_000000.002')
        make_diag_stick(tmp_path, backup_name='PagSWAct_backup_20250202_000000.002')
        assert gc.main([str(tmp_path), '--from-backup',
                        'PagSWAct_backup_20250202_000000.002', '--quiet']) == 0

    def test_warns_before_replacing_an_existing_activation_file(self, tmp_path, capsys):
        make_diag_stick(tmp_path)
        (tmp_path / 'PagSWAct.002').write_bytes(
            bytes(gc.build_record(VIN, '01060000', 0x0106, 0)))
        capsys.readouterr()
        assert gc.main([str(tmp_path), '--from-backup']) == 0
        assert 'overwrit' in capsys.readouterr().out.lower()

    def test_no_warning_when_there_is_nothing_to_replace(self, tmp_path, capsys):
        make_diag_stick(tmp_path)
        capsys.readouterr()
        gc.main([str(tmp_path), '--from-backup'])
        assert 'overwrit' not in capsys.readouterr().out.lower()

    def test_honours_no_xor(self, tmp_path):
        make_diag_stick(tmp_path)
        gc.main([str(tmp_path), '--from-backup', '--quiet', '--no-xor'])
        assert (tmp_path / 'copie_scr.sh').read_bytes() == gc.BOOTSTRAP.encode('utf-8')

    def test_cannot_be_combined_with_diag(self, tmp_path):
        assert gc.main([str(tmp_path), '--from-backup', '--diag', str(tmp_path)]) == 1


class TestPayloadFiles:
    """The ksh payloads live as real .sh files so .gitattributes' `*.sh text
    eol=lf` protects them -- as Python string literals they were outside it."""

    def _path(self, name):
        return os.path.join(REPO_ROOT, 'payloads', name)

    def test_run_activate_is_a_file(self):
        assert os.path.exists(self._path('run_activate.sh'))

    def test_run_diag_is_a_file(self):
        assert os.path.exists(self._path('run_diag.sh'))

    def test_the_file_is_what_the_module_serves(self):
        for fname, const in (('run_activate.sh', gc.RUN_ACTIVATE),
                             ('run_diag.sh', gc.RUN_DIAG)):
            with open(self._path(fname), encoding='utf-8', newline='') as f:
                assert f.read() == const, fname

    def test_payloads_use_lf_endings(self):
        for fname in ('run_activate.sh', 'run_diag.sh'):
            assert b'\r\n' not in open(self._path(fname), 'rb').read(), fname

    def test_payloads_start_with_the_ksh_shebang(self):
        for fname in ('run_activate.sh', 'run_diag.sh'):
            with open(self._path(fname), encoding='utf-8') as f:
                assert f.readline().rstrip('\n') == '#!/bin/ksh', fname


class TestVinValidation:
    """A VIN of the wrong length must be refused: it would silently produce
    codes from the wrong characters rather than fail."""

    def test_too_short_is_refused(self, tmp_path):
        assert gc.main(['WP1ZZZ', str(tmp_path), '--quiet']) == 1

    def test_too_long_is_refused(self, tmp_path):
        assert gc.main([VIN + 'X', str(tmp_path), '--quiet']) == 1

    def test_the_message_names_the_length(self, tmp_path, capsys):
        gc.main(['WP1ZZZ', str(tmp_path), '--quiet'])
        assert '17' in capsys.readouterr().err

    def test_nothing_is_written_for_a_bad_vin(self, tmp_path):
        gc.main(['WP1ZZZ', str(tmp_path), '--quiet'])
        assert not (tmp_path / 'PagSWAct.002').exists()

    def test_from_backup_also_refuses_a_bad_vin(self, tmp_path):
        make_diag_stick(tmp_path)
        assert gc.main(['WP1ZZZ', str(tmp_path), '--from-backup',
                        '--add', 'SDARS']) == 1

    def test_a_valid_vin_is_accepted_lowercase(self, tmp_path):
        assert gc.main([VIN.lower(), str(tmp_path), '--quiet']) == 0


class TestVinStructure:
    """Hard rules from ISO 3779/3780. Every one holds across the 28 real
    Porsche VINs in this repository."""

    def test_rejects_a_forbidden_letter(self):
        # Placed mid-VIN on purpose: at the end the numeric-tail rule would
        # fire first and the test would pass without exercising this one.
        for bad in ('WP1IZZ92ZFLA12345', 'WP1OZZ92ZFLA12345', 'WP1QZZ92ZFLA12345'):
            with pytest.raises(ValueError, match='ISO 3779'):
                gc.validate_vin(bad)

    def test_the_forbidden_letter_is_named(self):
        with pytest.raises(ValueError, match='I'):
            gc.validate_vin('WP1IZZ92ZFLA12345')

    def test_rejects_a_non_alphanumeric_character(self):
        with pytest.raises(ValueError):
            gc.validate_vin('WP1ZZZ92ZFLA-2345')

    def test_rejects_non_numeric_last_four(self):
        # ISO 3779 requires the final four characters to be numeric.
        with pytest.raises(ValueError):
            gc.validate_vin('WP1ZZZ92ZFLA123A5')

    def test_rejects_a_digit_in_first_position(self):
        # ISO 3780: position 1 is the geographic area, always a letter.
        with pytest.raises(ValueError):
            gc.validate_vin('1P1ZZZ92ZFLA12345')

    def test_still_rejects_the_wrong_length(self):
        with pytest.raises(ValueError):
            gc.validate_vin('WP1ZZZ')

    def test_accepts_every_real_vin_in_the_repository(self):
        for _row, vin, _name, _code in factory_cells():
            gc.validate_vin(vin)

    def test_uppercases_its_result(self):
        assert gc.validate_vin('wp1zzz92zfla12345') == 'WP1ZZZ92ZFLA12345'


class TestVinAdvisories:
    """Soft checks: they inform, they never block. Each one is advisory for a
    measured reason, not out of caution."""

    def test_a_plain_porsche_vin_draws_no_comment(self):
        assert gc.vin_advisories('WP1ZZZ92ZFLA12345') == []

    def test_flags_a_non_porsche_wmi(self):
        notes = gc.vin_advisories('WVWZZZ92ZFLA12345')
        assert notes and any('WVW' in n for n in notes)

    def test_names_volkswagen_for_a_wvw_vin(self):
        assert any('Volkswagen' in n for n in gc.vin_advisories('WVWZZZ92ZFLA12345'))

    def test_accepts_any_third_wmi_character(self):
        # WP0 sports cars, WP1 SUVs -- and whatever Porsche assigns next.
        for wmi in ('WP0', 'WP1', 'WP2', 'WP9'):
            assert gc.vin_advisories(wmi + 'ZZZ92ZFLA12345') == [], wmi

    def test_ignores_position_nine_when_it_is_a_filler(self):
        # 13 of 22 factory VINs carry 'Z' there: no check digit to verify.
        # This VIN is a 2008 car, so it draws the model-year note -- what
        # matters here is that no check-digit note appears alongside it.
        notes = gc.vin_advisories('WP0ZZZ97Z8L040010')
        assert not any('check digit' in n.lower() for n in notes), notes

    def test_flags_a_broken_check_digit(self):
        good = 'WP0AB2A78AL060050'
        assert gc.vin_advisories(good) == []
        broken = good[:8] + '7' + good[9:]
        assert any('check digit' in n.lower() for n in gc.vin_advisories(broken))

    def test_flags_a_model_year_outside_the_pcm31_era(self):
        notes = gc.vin_advisories('WP1ZZZ9PZ6LA46923')     # position 10 '6' = 2006
        assert any('2006' in n for n in notes)

    def test_accepts_the_2010_panameras_from_the_factory_data(self):
        for vin in ('WP0AB2A78AL060050', 'WP0AC2A78AL090033'):
            assert gc.vin_advisories(vin) == [], vin

    def test_every_repository_vin_from_the_pcm31_era_is_quiet(self):
        noisy = [v for _r, v, _n, _c in factory_cells()
                 if gc.vin_advisories(v) and v[9] in 'ABCDEFGHJ']
        assert not noisy, noisy


class TestVinAdvisoriesReachTheUser:
    def test_a_suspect_vin_is_reported_but_still_processed(self, tmp_path, capsys):
        assert gc.main(['WVWZZZ92ZFLA12345', str(tmp_path), '--quiet']) == 0
        assert 'WVW' in capsys.readouterr().err
        assert (tmp_path / 'PagSWAct.002').exists()

    def test_quiet_does_not_hide_them(self, tmp_path, capsys):
        gc.main(['WVWZZZ92ZFLA12345', str(tmp_path), '--quiet'])
        assert 'WVW' in capsys.readouterr().err

    def test_from_backup_reports_them_too(self, tmp_path, capsys):
        make_diag_stick(tmp_path, vin='WVWZZZ92ZFLA12345')
        gc.main(['WVWZZZ92ZFLA12345', str(tmp_path), '--from-backup',
                 '--add', 'SDARS', '--quiet'])
        assert 'WVW' in capsys.readouterr().err


class TestShowNamesTheModel:
    """The FeatureLevel SubID is the car's model identity -- the single most
    telling thing in a PagSWAct.002. --show must resolve it, not print the raw
    number."""

    def _row(self, capsys, name='FeatureLevel'):
        return next(l for l in capsys.readouterr().out.splitlines()
                    if l.strip().startswith(name))

    def test_names_the_model_behind_the_subid(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet', '--model', 'cayenne-se'])
        capsys.readouterr()
        gc.main(['--show', str(tmp_path)])
        assert 'Cayenne S E-Hybrid' in self._row(capsys)

    def test_names_a_different_model_correctly(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet', '--model', 'boxster-alt'])
        capsys.readouterr()
        gc.main(['--show', str(tmp_path)])
        assert 'Boxster' in self._row(capsys)

    def test_does_not_call_the_model_a_variant(self, tmp_path, capsys):
        # Every car carries its own FeatureLevel SubID, so "variant" and
        # "default" are the wrong words for it.
        gc.main([VIN, str(tmp_path), '--quiet', '--model', 'cayenne-se'])
        capsys.readouterr()
        gc.main(['--show', str(tmp_path)])
        row = self._row(capsys)
        assert 'variant' not in row.lower() and 'default' not in row.lower(), row

    def test_an_unmapped_subid_says_so(self, tmp_path, capsys):
        rec = gc.build_record(VIN, '010e0999', 0x010e, 0x0999)
        (tmp_path / 'PagSWAct.002').write_bytes(bytes(rec))
        gc.main(['--show', str(tmp_path)])
        row = self._row(capsys)
        assert '0x0999' in row and 'unknown' in row.lower(), row

    def test_other_features_still_get_the_variant_note(self, tmp_path, capsys):
        gc.main([VIN, str(tmp_path), '--quiet', '--subid', 'NavDBEurope=0x0001'])
        capsys.readouterr()
        gc.main(['--show', str(tmp_path)])
        assert 'map level 1' in self._row(capsys, 'NavDBEurope').lower()


REAL_VIN = 'WP0ZZZ98ZFS110814'          # from a diagnostic run on a 981 Boxster


def write_diag_output(tmp_path, vin=REAL_VIN, in_dump=True, in_log=True,
                      stamp='nodate'):
    """Recreate what run_diag.sh leaves on a stick."""
    if in_dump:
        d = tmp_path / f'pcm_dump_{stamp}'
        d.mkdir(exist_ok=True)
        (d / 'vin').write_text(vin + '\n')
    if in_log:
        (tmp_path / f'pcm_debug_{stamp}.log').write_text(
            '=== PCM Version ===\nPorsche_PCM3.1\n\n'
            f'=== VIN ===\n{vin}\n\n'
            '=== Existing Activation Files ===\n-rw-r--r-- PagSWAct.002\n')


class TestVinFromDiagnostics:
    """The diagnostic run copies /HBpersistence/vin onto the stick, so the VIN
    is already there and need not be typed again."""

    def test_reads_the_copy_in_the_dump_directory(self, tmp_path):
        write_diag_output(tmp_path, in_log=False)
        vin, source = gc.vin_from_diagnostics(str(tmp_path))
        assert vin == REAL_VIN and 'vin' in source

    def test_falls_back_to_the_log(self, tmp_path):
        write_diag_output(tmp_path, in_dump=False)
        vin, source = gc.vin_from_diagnostics(str(tmp_path))
        assert vin == REAL_VIN and 'pcm_debug' in source

    def test_prefers_the_dump_copy_over_the_log(self, tmp_path):
        write_diag_output(tmp_path)
        (tmp_path / 'pcm_dump_nodate' / 'vin').write_text('WP1ZZZ92ZFLA12345\n')
        vin, source = gc.vin_from_diagnostics(str(tmp_path))
        assert vin == 'WP1ZZZ92ZFLA12345', source

    def test_tolerates_trailing_whitespace(self, tmp_path):
        write_diag_output(tmp_path, in_log=False)
        (tmp_path / 'pcm_dump_nodate' / 'vin').write_text(f'  {REAL_VIN}  \r\n')
        assert gc.vin_from_diagnostics(str(tmp_path))[0] == REAL_VIN

    def test_nothing_to_find_is_not_an_error(self, tmp_path):
        assert gc.vin_from_diagnostics(str(tmp_path)) == (None, None)

    def test_rejects_an_error_message_in_place_of_a_vin(self, tmp_path):
        # The unit answers with a diagnostic line when the file is missing.
        (tmp_path / 'pcm_dump_nodate').mkdir()
        (tmp_path / 'pcm_dump_nodate' / 'vin').write_text(
            'cat: No such file or directory (/HBpersistence/vin)\n')
        assert gc.vin_from_diagnostics(str(tmp_path)) == (None, None)

    def test_rejects_a_structurally_invalid_vin(self, tmp_path):
        write_diag_output(tmp_path, vin='WP0IZZ98ZFS110814', in_log=False)
        assert gc.vin_from_diagnostics(str(tmp_path)) == (None, None)


class TestFromBackupUsesTheDetectedVin:
    def test_adding_needs_no_typed_vin_after_a_diagnostic_run(self, tmp_path):
        make_diag_stick(tmp_path, vin=REAL_VIN)
        write_diag_output(tmp_path)
        assert gc.main([str(tmp_path), '--from-backup', '--add', 'SDARS',
                        '--quiet']) == 0
        assert 0x0108 in [r[0] for r in records(tmp_path / 'PagSWAct.002')]

    def test_says_where_the_vin_came_from(self, tmp_path, capsys):
        make_diag_stick(tmp_path, vin=REAL_VIN)
        write_diag_output(tmp_path)
        gc.main([str(tmp_path), '--from-backup', '--add', 'SDARS'])
        out = capsys.readouterr()
        assert REAL_VIN in out.out + out.err

    def test_a_typed_vin_still_wins(self, tmp_path):
        make_diag_stick(tmp_path, vin=VIN)
        write_diag_output(tmp_path, vin=REAL_VIN)   # a different car on the stick
        # The typed VIN matches the backup, the detected one does not.
        assert gc.main([VIN, str(tmp_path), '--from-backup', '--add', 'SDARS',
                        '--quiet']) == 0

    def test_a_detected_vin_is_still_checked_against_the_backup(self, tmp_path):
        make_diag_stick(tmp_path, vin=VIN)          # backup signed for one car
        write_diag_output(tmp_path, vin=REAL_VIN)   # stick reports another
        assert gc.main([str(tmp_path), '--from-backup', '--add', 'SDARS']) == 1

    def test_without_diagnostics_it_still_asks_for_a_vin(self, tmp_path):
        make_diag_stick(tmp_path)
        assert gc.main([str(tmp_path), '--from-backup', '--add', 'SDARS']) == 1
