#!/usr/bin/env bash
# Crée le dépôt GitHub public et applique les réglages de sécurité de J1.
#
#   ./infra/github/setup-repo.sh <utilisateur-github> [nom-du-depot]
#
# Prérequis : gh (GitHub CLI) connecté avec `gh auth login`, dépôt local propre.
# Le script peut être relancé : chaque réglage est appliqué de nouveau, sans effet de bord.
set -euo pipefail

OWNER="${1:?Usage : $0 <utilisateur-github> [nom-du-depot]}"
NAME="${2:-snacki}"
REPO="${OWNER}/${NAME}"
BRANCH="main"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

command -v gh >/dev/null || { echo "Installez GitHub CLI : https://cli.github.com"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Lancez d'abord : gh auth login"; exit 1; }
if [ -n "$(git status --porcelain)" ]; then
  echo "Le dépôt local a des changements non commités : commitez-les ou mettez-les de côté."
  exit 1
fi

echo "1/6 Propriétaire dans CODEOWNERS et le lien de signalement"
if grep -rq "GITHUB_USER" .github/; then
  grep -rl "GITHUB_USER" .github/ | xargs sed -i.bak "s/GITHUB_USER/${OWNER}/g"
  find .github -name '*.bak' -delete
  git add .github
  # Dernier commit direct sur main, avant que la branche ne soit protégée.
  SKIP=no-commit-to-branch git commit -q -m "chore: propriétaire GitHub ${OWNER}"
fi

echo "2/6 Dépôt ${REPO}"
if gh repo view "$REPO" >/dev/null 2>&1; then
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/${REPO}.git"
  git push -u origin "$BRANCH"
else
  gh repo create "$REPO" --public --source . --remote origin --push \
    --description "PWA du snack Snacki (Nouadhibou) : FastAPI, Next.js, IA, DevSecOps"
fi
gh repo edit "$REPO" --add-topic pwa,fastapi,python,nextjs,devsecops,owasp,google-cloud-run

echo "3/6 Fusion : squash uniquement, branches supprimées après fusion, pas de wiki"
gh api -X PATCH "repos/${REPO}" \
  -F allow_merge_commit=false -F allow_rebase_merge=false -F allow_squash_merge=true \
  -F delete_branch_on_merge=true -F has_wiki=false >/dev/null

echo "4/6 Secrets, Dependabot, signalement privé"
gh api -X PATCH "repos/${REPO}" --input - >/dev/null <<'JSON'
{"security_and_analysis": {
  "secret_scanning": {"status": "enabled"},
  "secret_scanning_push_protection": {"status": "enabled"}}}
JSON
gh api -X PUT "repos/${REPO}/vulnerability-alerts" >/dev/null
gh api -X PUT "repos/${REPO}/automated-security-fixes" >/dev/null
gh api -X PUT "repos/${REPO}/private-vulnerability-reporting" >/dev/null

echo "5/6 Jeton des workflows en lecture seule par défaut"
gh api -X PUT "repos/${REPO}/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false >/dev/null

echo "6/6 Protection de la branche ${BRANCH}"
# Seul développeur : aucune approbation exigée (on ne peut pas approuver sa propre PR),
# mais PR obligatoire, portes CI vertes, branche à jour, conversations résolues.
gh api -X PUT "repos/${REPO}/branches/${BRANCH}/protection" --input - >/dev/null <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "checks": [{"context": "secrets"}, {"context": "quality"}, {"context": "tests"}, {"context": "api"}]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

echo
echo "Vérification :"
GH_TOKEN="$(gh auth token)" python3 scripts/verify_repo_security.py --repo "$REPO"
