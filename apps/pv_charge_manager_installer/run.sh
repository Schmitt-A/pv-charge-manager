#!/usr/bin/with-contenv bashio
set -euo pipefail

readonly repository_archive="https://github.com/Schmitt-A/pv-charge-manager/archive/refs/heads/main.tar.gz"
readonly work_dir="/tmp/pv-charge-manager"
readonly archive_path="${work_dir}/source.tar.gz"
readonly source_dir="${work_dir}/source/custom_components/pv_charge_manager"
readonly target_dir="/homeassistant/custom_components/pv_charge_manager"

install_integration() {
  if [[ ! -d /homeassistant ]]; then
    bashio::log.error "Home Assistant configuration is not mounted."
    return 1
  fi

  rm -rf "${work_dir}"
  mkdir -p "${work_dir}/source"

  bashio::log.info "Downloading PV Charge Manager from GitHub."
  curl --fail --location --retry 3 --silent --show-error \
    "${repository_archive}" \
    --output "${archive_path}"
  tar --extract --gzip --file "${archive_path}" \
    --directory "${work_dir}/source" \
    --strip-components=1

  if [[ ! -f "${source_dir}/manifest.json" ]]; then
    bashio::log.error "The downloaded repository does not contain the integration."
    return 1
  fi

  mkdir -p "${target_dir}"
  cp -R "${source_dir}/." "${target_dir}/"
  find "${target_dir}" -type d -name __pycache__ -prune -exec rm -rf {} +

  bashio::log.info "PV Charge Manager was installed in ${target_dir}."
  bashio::log.info "This app has no page. Stop it, then restart Home Assistant."
  bashio::log.info "Add the integration under Settings, Devices and services."
  bashio::log.info "The sidebar entry appears only after that integration exists."
}

code=0
install_integration || code=$?

# Exiting the command makes s6-linux-init start the container again.
# Halt so a one-shot install stays stopped.
if [[ -n "${S6_BASED_PATH:-}" && -x "${S6_BASED_PATH}/bin/halt" ]]; then
  mkdir -p /run/s6-linux-init-container-results
  echo "${code}" > /run/s6-linux-init-container-results/exitcode
  exec "${S6_BASED_PATH}/bin/halt"
fi
if [[ -x /run/s6/basedir/bin/halt ]]; then
  mkdir -p /run/s6-linux-init-container-results
  echo "${code}" > /run/s6-linux-init-container-results/exitcode
  exec /run/s6/basedir/bin/halt
fi
exit "${code}"
