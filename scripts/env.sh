## @file       env.sh
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
#   @details     Provides environment variables for MSC-LDK.sh

## @brief The base directory where msc_ldk is installed in.

export MSC_LDK_ROOT=$(readlink -f $(dirname $(readlink -f $0))/..)

# When used by msc-ldk-maintainer.git, it points to sources/msc-ldk-maintainer.git
# So find top level dir within msc-ldk.git
while [ ! -e "${MSC_LDK_ROOT}/scripts/based_on_yocto.txt" ]; do
    MSC_LDK_ROOT=$(readlink -f "${MSC_LDK_ROOT}/..")

    if [ "${MSC_LDK_ROOT}" == "/" ]; then
        failure "Not in an MSC-LDK directory"
    fi
done

## @brief Where all our sources are stored.
export MSC_LDK_SOURCES="${MSC_LDK_ROOT}/sources"

## @brief Directory where the builds are performed
export MSC_LDK_BUILD_ROOT="${MSC_LDK_ROOT}/build"

## @brief Local path where yocto is checked out to.
export MSC_LDK_YOCTO_ROOT="${MSC_LDK_SOURCES}/yocto.git"

## @brief Path to the MSC-LDK template files
export MSC_LDK_TEMPLATE_ROOT="${MSC_LDK_ROOT}/template"

## @brief Path where the yocto downloads will be stored. Can be predefined when calling setup.sh
export MSC_LDK_YOCTO_DL_DIR=${MSC_LDK_YOCTO_DL_DIR:-"${MSC_LDK_ROOT}/downloads"}

## @brief Path where the yocto shared states (e.g. buold packages). Can be predefined when calling setup.sh
export MSC_LDK_YOCTO_SSTATE_DIR=${MSC_LDK_YOCTO_SSTATE_DIR:-"${MSC_LDK_ROOT}/sstate-cache"}

## @brief Yocto branch MSC-LDK is based on.
export MSC_LDK_BASED_ON_YOCTO_BRANCH=$(< "${MSC_LDK_ROOT}/scripts/based_on_yocto.txt")

## @brief Path to maintainer script repository
export MSC_LDK_MAINTAINER="${MSC_LDK_SOURCES}/msc-ldk-maintainer.git"
