"""Offline release checks: no USB, no motors, no speech services."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ReleaseIntegrityTests(unittest.TestCase):
    def test_trained_checkpoint_hashes(self):
        lines = (ROOT / 'MODEL_SHA256SUMS').read_text().splitlines()
        self.assertGreaterEqual(len(lines), 4)
        for line in lines:
            expected, relative_path = line.split('  ', 1)
            with self.subTest(path=relative_path):
                path = ROOT / relative_path
                self.assertTrue(path.is_file(), f'Missing model: {relative_path}')
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)

    def test_arduino_sketch_and_code_exist(self):
        for relative_path in [
            'Arduino/Robot_Car_Bilingual_Safe/Robot_Car_Bilingual_Safe.ino',
            'app.py', 'motor_link.py', 'recognizer.py',
            'research_dual_models/dual_recognizer.py',
            'research_dual_models/evaluation.json',
        ]:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

if __name__ == '__main__':
    unittest.main()
