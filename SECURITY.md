# Security and public-repository audit

## Audit scope

On **21 November 2026**, the public repository was cloned independently and checked through commit `f9d1849b476ef76609c09f7060acf1e6d83ac4b0`:

- 88 reachable commits and 423 historical blobs across the advertised Git refs.
- Gitleaks **8.30.1**, downloaded from its official release with the published SHA-256 checksum verified, scanned the Git history with output redacted.
- Additional checks covered provider-token patterns, complete private-key PEM blocks, OAuth grant URLs and signed download URLs. Published ZIP contents and the historical base64 presentation transfer were decoded for inspection.
- Tracked history was checked for private configuration, `.env`, signing-key files, source databases and the organizer's dataset files.

**Result: no confirmed API key, authentication token or private signing key was detected in this scope.** The 28 initial generic-key matches were inspected individually: all were `translation_key` fields containing public article IDs. The committed scanner configuration allows only that exact metadata field, path and article-ID format; it does not disable generic API-key detection elsewhere.

The audit also found no complete organizer article or copied paragraph of at least 500 characters in the inspected historical JSON string fields. That is a limited exact-content check, not a legal review or a guarantee that every possible quotation has been identified.

The [machine-readable audit summary](docs/security-audit.json) records the counts and scope. A synthetic credential test also confirmed that the narrow article-ID allowlist still permits detection of an API-key-shaped value in another field in the same file.

Static scanning cannot prove that a credential has never been exposed elsewhere. This audit does not inspect private n8n credential storage, account logs, deleted remote refs, external forks, local untracked files, or secrets spoken inside audio. If a real credential is ever published, revoke or rotate it; removing its current file does not remove Git history or external copies.

## Ongoing checks

The **Secret scan** GitHub Actions workflow checks full fetched history on pushes and pull requests, without provider keys. It uses a pinned scanner release and verifies the archive checksum before execution. To run the same check locally:

```bash
python scripts/scan-secrets.py
```

Do not publish unredacted scanner reports or paste credentials into issues. Report suspected exposure to the repository owner privately through GitHub.

## Credential boundary

- OpenAI and ElevenLabs API keys belong in n8n credentials, not frontend code or exported workflows.
- `.secrets/n8n-signing.pem` is a private, installation-specific signing key and must stay local. Workflow signature-verification **public keys** are intentionally public.
- Voice IDs, article IDs, workflow IDs and credential names are identifiers, not authentication secrets. Published webhook addresses still require the configured signature checks; they are not a replacement for authentication.
- `.env`, `.secrets/`, `data/` and private generation manifests are ignored. Inspect staging before publishing: force-added files bypass `.gitignore`.
- Keep the API bound to `127.0.0.1` for this demo. Demo profile switching is not production authentication; do not expose the local API as a multi-user public service without adding access controls.
