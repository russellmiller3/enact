"""Built-in reusable policy functions."""

from enact.policies.email import no_mass_emails, no_repeat_emails
from enact.policies.cloud_storage import dont_delete_without_human_ok
from enact.policies.filesystem import (
    dont_edit_gitignore,
    dont_read_env,
    dont_touch_ci_cd,
    dont_access_home_dir,
    dont_copy_api_keys,
)
from enact.policies.git import (
    dont_force_push,
    require_meaningful_commit_message,
    dont_commit_api_keys,
)
from enact.policies.prompt_injection import (
    block_prompt_injection,
    block_prompt_injection_fields,
)
from enact.policies.credential import (
    pause_on_resource_purpose_mismatch,
    CREDENTIAL_POLICIES,
)
from enact.policies.url import (
    block_dns_exfil_domains,
    block_suspicious_tlds,
    block_raw_ip_urls,
    require_https,
    webfetch_domain_allowlist,
    URL_POLICIES,
)
