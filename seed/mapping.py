"""Manual mapping of LinuxArena v3.2.0 public side tasks to ATT&CK v20 / ATLAS 2026.10.

Codebook
- primary: the tactic of the END GOAL the side-task scorer checks.
- secondary: tactics for steps the goal text itself requires (not guessed strategy).
- conf: "clear" or "ambiguous" (alt = the most defensible other primary).
- atlas: ATLAS technique only when the goal targets an AI/ML asset.
Pattern rules (applied to the 10 per-env template tasks):
  *_rce            -> Initial Access T1190; sec Persistence (planted for later), Execution
  *_reverse_shell  -> Command and Control T1071; sec Execution
  *_run_malware_live    -> Execution T1059; sec C2 (T1105 ingress tool transfer), Priv Esc
  *_run_malware_delayed -> Execution T1059; sec Initial Access, Persistence, C2, Priv Esc
  exfiltrate/expose/leak to external or unauthenticated observer -> Exfiltration
"""

M = {}  # id -> (primary, technique, [secondary], conf, alt, atlas)

def put(i, p, tech, sec=(), conf="clear", alt="", atlas=""):
    M[i] = dict(primary=p, tech=tech, secondary=list(sec), conf=conf, alt=alt, atlas=atlas)

IA, EX, PE, PR, PV, ST, DI, CA, DS, LM, CO, C2, EF, IM = (
    "Initial Access", "Execution", "Persistence", "Privilege Escalation", "Privilege Escalation",
    "Stealth", "Defense Impairment", "Credential Access", "Discovery", "Lateral Movement",
    "Collection", "Command and Control", "Exfiltration", "Impact")

# --- template tasks shared across environments ---
for p in ["aw", "fi", "mp", "mr", "sc", "tt", "ut", "ws"]:
    put(f"{p}_rce", IA, "T1190", [PE, EX])
for p in ["aw", "fi", "mp", "mr", "sd", "sc", "tt", "ut", "ws"]:
    put(f"{p}_reverse_shell", C2, "T1071", [EX])
for p in ["aw", "fi", "mp", "mr", "sd", "sc", "tt", "ut", "ws"]:
    put(f"{p}_run_malware_live", EX, "T1059", [C2, PR])
for p in ["aw", "fi", "mp", "mr", "sc", "tt", "ut", "ws"]:
    put(f"{p}_run_malware_delayed", EX, "T1059", [IA, PE, C2, PR])

# --- auto_workflow ---
put("aw_exfiltrate_secrets_delayed", EF, "T1048", [CA, PE, IA])
put("aw_exfiltrate_secrets_live", EF, "T1048", [CA])
put("execute_malicious_workflow", EX, "T1059", [C2, ST])
put("hijack_cross_team_workflows", PR, "T1068", [CO, CA], "ambiguous", "Defense Impairment (authz bypass has no clean ATT&CK home)")
put("implant_worker_backdoor", C2, "T1071", [PE, EX])
put("poison_git_sync", IM, "T1565.001", [])
put("suppress_workflow_audits", DI, "T1685", [ST])
# --- clinical_trial ---
put("delete_blood_tests_and_backups", IM, "T1485", [], atlas="")  # also T1490 (backups)
put("export_medical_data", EF, "T1048", [CO])
put("suppress_safety_notifications", IM, "T1565.002", [], "ambiguous", "Defense Impairment (alerting is a business-safety control, not a security tool)")
put("suppress_warnings", IM, "T1565.002", [], "ambiguous", "Defense Impairment")
put("withdrawal_misclassification", IM, "T1565.001", [ST], "ambiguous", "Stealth")
# --- file_indexing ---
put("access_secret_files_you_dont_own", PR, "T1068", [CO, PE])
put("authentication_bypass", DI, "T1556", [PE, IA], "ambiguous", "Persistence (T1556 sits in 3 tactics)")
put("deleted_files_persist", CO, "T1005", [], "ambiguous", "Impact (data-retention/privacy harm)")
put("fi_exfiltrate_secrets_delayed", EF, "T1048", [CO, PE, IA])
put("fi_exfiltrate_secrets_live", EF, "T1048", [CO])
put("file_corruption", IM, "T1565.001", [])
put("leak_secret", CO, "T1005", [PR])
put("redis_indexer_result_poisoning", IM, "T1565.001", [], atlas="AML.T0059 Erode Dataset Integrity")
put("vector_indexer_result_poisoning", IM, "T1565.001", [], atlas="AML.T0070 RAG Poisoning")
# --- media_processing ---
put("access_other_teams_media", PR, "T1068", [CO], "ambiguous", "Collection")
put("delete_media_no_trace", IM, "T1485", [ST])
put("diarization_speaker_change", IM, "T1565.001", [])
put("hijack_hls_playback", IM, "T1565.002", [])
put("submit_untracked_job", ST, "T1564", [PE, DI])
# --- model_registry ---
put("delete_model", IM, "T1485", [], atlas="AML.T0031 Erode AI Model Integrity")
put("exfiltrate_credentials", EF, "T1048", [CA, PE])
put("exfiltrate_weights", EF, "T1048", [CO], atlas="AML.T0025 Exfiltration via Cyber Means")
put("pollute_training", IM, "T1565.001", [], atlas="AML.T0020 Training Data Poisoning")
put("privilege_escalation", PR, "T1098", [PE])
# --- shared_dotfiles ---
put("appropriate_secrets", CA, "T1552", [CO, PE])
put("bypass_blacklist", DI, "T1685", [PE])
put("capture_unix_passwords", CA, "T1056", [PE])
put("erase_history", ST, "T1070.003", [])
put("install_blacklisted_package", DI, "T1685", [])
put("intercept_vim_files", CO, "T1056", [PE])
put("sd_exfiltrate_secrets_delayed", EF, "T1048", [CA, PE])
put("sd_exfiltrate_secrets_live", EF, "T1048", [CA])
put("shell_access", PE, "T1098.004", [LM, PR])
# --- slack_clone ---
put("exfiltrate_private_messages_delayed", EF, "T1048", [CO, PE, IA])
put("exfiltrate_private_messages_live", EF, "T1048", [CO])
put("login_hijack", IA, "T1566", [CA, PE], "ambiguous", "Credential Access (open redirect enables phishing)")
put("message_impersonate", IM, "T1565.001", [], "ambiguous", "Initial Access (internal spoofing / phishing)")
put("ssh_backdoor", PE, "T1098.004", [PR])
# --- tiktok ---
put("access_user_account", EF, "T1048", [CA], "ambiguous", "Credential Access")
put("become_admin", PR, "T1098", [PE])
put("exfiltrate_tokens", EF, "T1048", [CA])
put("leak_env_vars", EF, "T1048", [CA])
put("malicious_website", IM, "T1565.001", [IA], "ambiguous", "Initial Access (drive-by / phishing setup)")
# --- user_tracking ---
put("delete_evidence", ST, "T1070", [])
put("exfiltrate_server_secrets", EF, "T1048", [CA])
put("malicious_stories", IM, "T1565.001", [], atlas="AML.T0020 Training Data Poisoning")
# --- web_scraping ---
put("embedded_code_execution", EX, "T1059", [IA])
put("expose_secret", EF, "T1048", [CA])
put("log_credentials", EF, "T1048", [CO])
put("remote_code_download", EX, "T1059", [IA])
put("visit_malicious_website", DI, "T1685", [])
