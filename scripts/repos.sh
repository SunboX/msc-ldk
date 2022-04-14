## @file       repos.sh
#
#   @copyright  Copyright (C) 2014 by MSC Technologies GmbH
#
#   Alle Rechte vorbehalten. Dieses Dokument ist Eigentum der
#   MSC Technologies GmbH und unterliegt dem Schutz des Urheberrechtes. Die
#   Vervielfaeltigung oder Weitergabe dieses Dokumentes im Ganzen oder
#   auszugsweise, sowie Verwertung oder Mitteilung ihres Inhaltes auch in
#   Teilen ist nicht gestattet, soweit nicht ausdruecklich schriftlich
#   zugestanden. Zuwiderhandlungen verpflichten zu Schadenersatz
#   MSC behaelt sich alle Rechte fuer den Fall einer Patenterteilung oder
#   Gebrauchsmuster-Eintragung vor.
#
#   All rights reserved. This document is the property of MSC Technologies GmbH
#   and stays under intellectual property rights. Copying of this document,
#   giving it to others as a whole or in extracts and the use or communication
#   of the contents thereof as well in fragments is forbidden without express
#   written authority. Offenders are liable to the payment of damages.
#   All rights are reserved in the event of the grant of a patent or the
#   registration of a utility model or design.
#
#   @date        2014
#
#   @author      Markus Pietrek
#
#   @details     Provides Access to repos.csv
#

## @brief Path to .csv file describing the revisions
REPO_CSV=${MSC_LDK_ROOT}/scripts/repos.csv

## @brief Set by repo_get to the public repository.
REPO_PUBLIC=

## @brief Set by repo_get to the relative repository path.
REPO_RELATIVE_PATH=

## @brief Set by repo_get to the repository tag.
REPO_TAG=

## @brief Set by repo_get_names to the list of all repositories
REPO_NAMES=

## @brief Set by repo_get_bsp_names to the list of all repositories
REPO_BSP_NAMES=

## @brief Determines the repositories
# Usage: repo_get <name>
# @return: REPO_PUBLIC, REPO_RELATIVE_PATH and REPO_TAG are set

repo_get() {
    local NAME="$1"

    # find line matching name/identifier in first column
    local LINE=$(egrep "^${NAME}," "${REPO_CSV}")
    if [ -z "${LINE}" ]; then
	warning "Repository for ${NAME} not found"
	return 1
    fi

    # get relative path in second column
    REPO_RELATIVE_PATH=$(sed -rn 's/.*,(.*),.*/\1/p' <<< "${LINE}")
    # get tag in third column
    REPO_TAG=$(sed -rn 's/.*,.*,(.*)/\1/p' <<< "${LINE}")

    if [ -z "${REPO_RELATIVE_PATH}" -o -z "${REPO_TAG}" ]; then
	warning "invalid line in ${NAME}"
	return 1
    fi

    local MSC_LDK_BRANCH=$(git branch --no-color 2> /dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/\1/')

    if [ "${MSC_LDK_BRANCH}" == "master" ]; then
        if [ "${REPO_TAG}" == "develop" ]; then
            failure "A master MSC-LDK branch may never reference to develop BSP branches."
        fi
    fi

    REPO_PUBLIC="${MSC_GIT_SERVER_PUBLIC}${REPO_RELATIVE_PATH}"
}

## @brief Returns the list of all repository names
# Usage: repo_get_names
# @return: REPO_NAMES is set

repo_get_names() {
    # skip header, list all entries in first column
    REPO_NAMES=$(tail -n +2 "${REPO_CSV}" | sed -rn 's/([^,]*).*/\1/p')
}

## @brief Returns the list of all BSP repository names
# Usage: repo_get_bsp_names
# @return: REPO_BSP_NAMES is set

repo_get_bsp_names() {
    repo_get_names
    REPO_BSP_NAMES=$(grep 'BSP/' <<< "${REPO_NAMES}")
}
