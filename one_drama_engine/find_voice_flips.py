import glob, json

files = sorted(glob.glob("storage/tts_output/ep_*/recap_script.json"))
print(f"Checking {len(files)} recap_script.json files...")

count = 0
for fp in files:
    with open(fp, "r", encoding="utf-8") as f:
        data = json.load(f)
    for i in range(1, len(data) - 1):
        prev_s = data[i-1]
        curr_s = data[i]
        next_s = data[i+1]
        
        gap_before = curr_s.get("start", 0) - prev_s.get("end", 0)
        gap_after = next_s.get("start", 0) - curr_s.get("end", 0)
        
        # Female speech interrupted by a single rogue male segment
        if prev_s.get("gender") == "female" and next_s.get("gender") == "female" and curr_s.get("gender") == "male":
            count += 1
            print(f"\n[FLIP #{count}] {fp} Seg ID={curr_s.get('id')}:")
            print(f"   Prev ({prev_s.get('speaker')}, {prev_s.get('gender')}): {prev_s.get('recap_text')} | orig: {prev_s.get('original_text')}")
            print(f"   Curr ({curr_s.get('speaker')}, {curr_s.get('gender')}): {curr_s.get('recap_text')} | orig: {curr_s.get('original_text')} (pitch: {curr_s.get('pitch_hz')}Hz, ac_gen: {curr_s.get('acoustic_gender')}, matched_role: {curr_s.get('matched_role')})")
            print(f"   Next ({next_s.get('speaker')}, {next_s.get('gender')}): {next_s.get('recap_text')} | orig: {next_s.get('original_text')}")
            print(f"   Timing gap: prev->curr = {gap_before:.2f}s, curr->next = {gap_after:.2f}s")
