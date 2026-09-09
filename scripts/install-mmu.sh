#!/usr/bin/env bash
# Installe la commande "mmu" pour l'utilisateur courant, sans pip install.
#
# Ce script ne fait qu'une chose: ajouter <depot>/bin au PATH de l'utilisateur,
# de facon permanente (nouveau terminal) et idempotente (relancable sans
# dupliquer la ligne). Le raccourci lui-meme -- `bin/mmu` -- porte deja tout ce
# qu'il faut (PYTHONPATH calcule depuis sa propre position, cf. son en-tete).
#
# A lancer UNE FOIS: `bash scripts/install-mmu.sh`.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bin_dir="${repo_root}/bin"

if [ ! -x "${bin_dir}/mmu" ]; then
    echo "Erreur: ${bin_dir}/mmu introuvable ou non executable. Depot incomplet ?" >&2
    exit 1
fi

# Detection du fichier de configuration du shell interactif. $SHELL est le
# shell de connexion de l'utilisateur, pas necessairement celui qui execute ce
# script (invoque via `bash ...`) -- c'est le bon a lire, puisque c'est celui
# qui chargera la ligne ajoutee au prochain terminal.
case "${SHELL:-}" in
    */zsh) rc_file="${HOME}/.zshrc" ;;
    */bash) rc_file="${HOME}/.bashrc" ;;
    *) rc_file="${HOME}/.profile" ;;
esac

marker_line="export PATH=\"${bin_dir}:\$PATH\""

if [ -f "${rc_file}" ] && grep -qF "${bin_dir}" "${rc_file}"; then
    echo "Deja installe: ${bin_dir} est deja reference dans ${rc_file}."
else
    {
        printf '\n# mixed_media_utility: commande "mmu" (installe par scripts/install-mmu.sh)\n'
        printf '%s\n' "${marker_line}"
    } >> "${rc_file}"
    echo "Installe: ligne ajoutee a ${rc_file}."
fi

echo ""
echo "Ouvre un NOUVEAU terminal (ou lance: source ${rc_file}), puis teste:"
echo "    mmu --help"
