---
name: git-clone-accelerator
description: Use when cloning GitHub repositories or generating git clone commands in environments where direct GitHub access may be slow or unreliable. Rewrites GitHub clone URLs through the https://git.d8b.co/ acceleration prefix before running or recommending git clone.
---

# Git Clone Accelerator

Use this skill whenever you need to clone a GitHub repository or provide a `git clone` command for a GitHub URL.

## Rule

For GitHub repositories, prefix the clone URL with:

```text
https://git.d8b.co/
```

## URL Rewrite

Rewrite:

```text
https://github.com/<owner>/<repo>.git
```

to:

```text
https://git.d8b.co/https://github.com/<owner>/<repo>.git
```

If the original URL has no `.git` suffix, preserve that style:

```text
https://github.com/<owner>/<repo>
```

becomes:

```text
https://git.d8b.co/https://github.com/<owner>/<repo>
```

## Examples

```bash
git clone https://git.d8b.co/https://github.com/addyosmani/agent-skills.git
git clone https://git.d8b.co/https://github.com/Fission-AI/OpenSpec.git
git clone https://git.d8b.co/https://github.com/github/spec-kit.git
```

## When To Apply

Apply this automatically when:

* the user asks to clone a GitHub repository;
* a document references a GitHub repository that must be cloned locally;
* you are preparing setup instructions that include `git clone https://github.com/...`;
* direct GitHub access may fail, be slow, or be blocked.

## When Not To Apply

Do not rewrite:

* non-GitHub URLs;
* SSH clone URLs such as `git@github.com:owner/repo.git`, unless converting to HTTPS is acceptable for the task;
* local paths;
* already accelerated URLs starting with `https://git.d8b.co/`.

## Fallback

If the accelerated URL fails, retry the original GitHub URL only if cloning is still necessary and the user has allowed network access.

When reporting what was done, mention that the GitHub URL was cloned through the acceleration prefix.
