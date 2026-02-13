# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause


cd ../
./create_docker.sh

fw-beta gear build .
fw-beta gear config --new
fw-beta gear config --input gre_data=flywheel/MEGRE_uw_sag_protocol.zip

fw-beta gear run --prepare -d flywheel/local_run/

fw-beta gear run flywheel/local_run

# If gear is successful and ready to upload, run the following command:
# fw-beta gear upload