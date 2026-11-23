"""Quick validation that models and training pipeline can be imported."""
from recognizer import BilingualRecognizer, english_action_from_text
r = BilingualRecognizer()
assert english_action_from_text('forward') == 'F'
assert english_action_from_text('turn left') == 'L'
assert english_action_from_text('backwards') == 'B'
assert english_action_from_text('halt') == 'S'
assert english_action_from_text('hello how are you') is None
s = r.status()
print('Balochi trained classifier:', 'OK' if s['balochi_available'] else 'MISSING')
print('English Vosk:', 'OK' if s['english_available'] else 'UNAVAILABLE: '+str(s['english_issue']))
print('Recognition modes: auto / english / balochi')
