## @file       msc_lib.sh
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
#   @details     Provides helper functions.
#                Color settings can be overwritten by user by defining
#                COLOR_ERROR, COLOR_OK etc.

VERBOSE=
OUTPUT=
LOG_FILE=
USE_SYSLOG=
SYSLOG_FACILITY=local0

if [ -n "${USE_SYSLOG_WHEN_NOT_ON_TERMINAL}" ]; then
    if [ -a "${TERM}" == "dumb" -o -n "${TERM}" ]; then
    # dumb terminal is set when executing background scripts within udev
        USE_SYSLOG=1
    fi
fi

# we use stdout as stderr to not break compatiblity with existing scripts
# and regression tests.
STDERR=${STDOUT}


# provide color settings
COLOR_RED="\e[0;31m"
COLOR_GREEN="\e[0;32m"
COLOR_INFO="\e[0;36m"
COLOR_YELLOW="\e[1;33m"
COLOR_DARK_GRAY="\e[1;30m"
COLOR_DEFAULT="\e[0m"

if [ -t 1 ]; then
    # output is on terminal, provide colors
    COLOR_err=$COLOR_RED
    COLOR_info=$COLOR_INFO
    COLOR_notice=$COLOR_GREEN
    COLOR_warn=$COLOR_YELLOW
    COLOR_debug=$COLOR_DARK_GRAY
else
    # output is redirected, avoid colors
    COLOR_err=
    COLOR_info=
    COLOR_notice=
    COLOR_warn=
    COLOR_debug=
    COLOR_DEFAULT=
fi

## @brief Prints a message. When on a terminal, the message is printed colorized. When not on a terminal and USE_SYSLOG_WHEN_NOT_ON_TERMINAL is set, syslogd is used.
## Usage: message "message" "err|info|notice|warn|debug"

message() {
    MSG="$1"
    TYPE="$2"

    if [ -n "${USE_SYSLOG}" ]; then
        logger -p "${SYSLOG_FACILITY}.${TYPE}" "$0: ${MSG}"
    else
        eval COLOR=\$COLOR_${TYPE}
        echo -e "${COLOR}${MSG}${COLOR_DEFAULT}"
    fi
}

## @brief Prints an error message and aborts script.

failure() {
    message "ERROR: $1" err
    exit 1
}

## @brief Prints an warning.

warning() {
    message "WARNING: $1" warn
}

## @brief Prints an information.

info() {
    message "INFO: $1" info
}

## @brief Prints "OK".

ok() {
    message "*** OK ***" notice
}

## @brief Prints a verbose message when variable VERBOSE is set

verbose() {
    if [ "$VERBOSE" = "1" ]; then
        message "$1" debug
    fi
}

## @brief Prints the script's usage and aborts.

usage() {
    if [ "$1" != "" ]; then
        message "ERROR: $1" err
    fi

    message "$USAGE" notice
    exit 1
}

## @brief Replaces text matching regular expression in files
#
# Usage: replace_text_in_file file reg_pattern replacement
replace_text_in_file() {
    sed "s;$2;$3;" <$1 >$1.sed || \
        failure "sed"
    chmod --reference=$1 $1.sed || \
        failure "chmod"
    mv $1.sed $1 || \
        failure "mv"
}

## @brief Parses optional argument and stories it in variable
#
# Usage: optvar &lt;variable&gt; --SOMETHING=&lt;value&gt;
#
# @return variable is set to value.

optvar() {
    local VAL=$(echo "$2" |sed 's/[-_a-zA-Z0-9]*=//')

    # workaround for busybox which doesn't have declare
    # declare -p $1 $VAL
    local TMPFILE=/tmp/optvar.$$
    echo $VAL >${TMPFILE}
    read $1 <${TMPFILE}
    rm -f ${TMPFILE}

    eval $1_PRESENT=1
}
