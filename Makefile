#
# @file       Makefile
#
#    @copyright  Copyright (C) 2014 by MSC Vertriebs GmbH
#
#    Alle Rechte vorbehalten. Dieses Dokument ist Eigentum der
#    MSC Vertriebs GmbH und unterliegt dem Schutz des Urheberrechtes. Die
#    Vervielfaeltigung oder Weitergabe dieses Dokumentes im Ganzen oder
#    auszugsweise, sowie Verwertung oder Mitteilung ihres Inhaltes auch in
#    Teilen ist nicht gestattet, soweit nicht ausdruecklich schriftlich
#    zugestanden. Zuwiderhandlungen verpflichten zu Schadenersatz
#    MSC behaelt sich alle Rechte fuer den Fall einer Patenterteilung oder
#    Gebrauchsmuster-Eintragung vor.
#
#    All rights reserved. This document is the property of MSC Vertriebs GmbH
#    and stays under intellectual property rights. Copying of this document,
#    giving it to others as a whole or in extracts and the use or communication
#    of the contents thereof as well in fragments is forbidden without express
#    written authority. Offenders are liable to the payment of damages.
#    All rights are reserved in the event of the grant of a patent or the
#    registration of a utility model or design.
#
#    @date        2014
#
#    @author      Markus Pietrek
#

BSPS ?= $(filter-out lost+found, $(notdir $(wildcard ./build/*)))
BSPS_BUILD = $(patsubst %,bsp_%_build,$(BSPS))
BSPS_TEST = $(patsubst %,bsp_%_test,$(BSPS))
BSPS_INSTALL = $(patsubst %,bsp_%_install,$(BSPS))
DESTDIR ?= /usr/local/msc-ldk
DESTDIR_DOC = ${DESTDIR}/share/doc/msc_ldk
YOCTO_DOC_BASE = sources/yocto.git/documentation/
BITBAKE_DOC_BASE = sources/yocto.git/bitbake/doc

# keep this in-sync with doc/main.dox:Links
YOCTO_DOC = \
	${YOCTO_DOC_BASE}/bsp-guide/bsp-guide.tgz     \
	${YOCTO_DOC_BASE}/dev-manual/dev-manual.tgz   \
	${YOCTO_DOC_BASE}/kernel-dev/kernel-dev.tgz   \
	${YOCTO_DOC_BASE}/mega-manual/mega-manual.tgz \
	${YOCTO_DOC_BASE}/profile-manual/profile-manual.tgz \
	${YOCTO_DOC_BASE}/ref-manual/ref-manual.tgz    \

BITBAKE_DOC = \
	${BITBAKE_DOC_BASE}/bitbake-user-manual/bitbake-user-manual.tgz \

include scripts/Makefile.in

all: build/ $(BSPS_BUILD)

build:
	scripts/setup.sh

.PHONY: test
test: $(BSPS_TEST)

.PHONY: install
install: install_doc install_images

.PHONY: install_doc
install_doc: doc
	$Q for doc in ${YOCTO_DOC}; do \
		mkdir -p ${DESTDIR_DOC}/yocto/`basename $${doc} .tgz`; \
		tar xf $${doc} -C ${DESTDIR_DOC}/yocto/`basename $${doc} .tgz`; \
	done

.PHONY: $(BSPS_BUILD)
$(BSPS_BUILD):
	$Q make -C build/$(patsubst bsp_%_build,%,$@) all

.PHONY: install_images
install_images: $(BSPS_INSTALL)

.PHONY: $(BSPS_INSTALL)
$(BSPS_INSTALL):
	$Q make -C build/$(patsubst bsp_%_install,%,$@) install DESTDIR=${DESTDIR}

.PHONY: $(BSPS_TEST)
$(BSPS_TEST):
	$Q make -C build/$(patsubst bsp_%_test,%,$@) test

# MSC-LDK documentation is provided as a separate .PDF
.PHONY: doc
doc: yocto-doc bitbake-doc
	$Q for doc in ${YOCTO_DOC}; do \
		mkdir -p doc/yocto/`basename $${doc} .tgz`; \
		tar xf $${doc} -C doc/yocto/`basename $${doc} .tgz`; \
	done
	$Q echo "Documentation has been unpacked to doc/"

# build yoctos internal documentation
yocto-doc: ${YOCTO_DOC}
${YOCTO_DOC}:
	cd ${YOCTO_DOC_BASE} && make DOC=`basename $@ .tgz`
# .pdf is not supported in all documentation groups, but where it is it supported, is required for tarballs, so we ignore errors generating pdf
	cd ${YOCTO_DOC_BASE} && make pdf DOC=`basename $@ .tgz` || true
	cd ${YOCTO_DOC_BASE} && make tarball DOC=`basename $@ .tgz`

bitbake-doc: ${BITBAKE_DOC}
${BITBAKE_DOC}:
	cd ${BITBAKE_DOC_BASE} && make DOC=`basename $@ .tgz`
	cd ${BITBAKE_DOC_BASE} && make tarball DOC=`basename $@ .tgz`

.PHONY:
clean:
	$@ rm -rf doc/html
	$@ rm -f ${YOCTO_DOC}
