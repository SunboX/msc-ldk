#! /bin/bash
#
## @file       build.sh
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
#   @details     Builds a project using bitbake. Provides a wrapper for git.
#                This file should be symlinked from build.sh to build.bsp.sh
#

# load helper files from msc-ldk/scripts/
. $(dirname $(readlink -f $0))/msc_lib.sh
. $(dirname $(readlink -f $0))/env.sh

# This file is 
USAGE="Usage: build.sh [OPTIONS]
Builds an MSC-LDK image.

Usage:
 build.sh bitbake <same arguments as bitbake>
 build.sh runqemu qemux86
"

if [ -z "$*" ]; then
    usage
fi

. ${MSC_LDK_YOCTO_ROOT}/oe-init-build-env . >/dev/null 2>&1 || \
    failure "can't set environment variables"

$@ || \
    failure "$*"

ok

