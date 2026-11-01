// Consent-first location. We explain why BEFORE the browser's own prompt appears,
// and always offer "Not now". The exact position is returned to the caller only;
// callers convert it to a ~150 m area code before anything leaves the device.

export class LocationError extends Error {
  constructor(message, code) {
    super(message);
    this.code = code; // "cancelled" | "denied" | "unavailable" | "timeout" | "unsupported"
  }
}

const MESSAGES = {
  denied: "Your browser didn't share your location.",
  unavailable: "We couldn't work out where you are right now. Try again near a window or with Wi-Fi on.",
  timeout: "Finding your location took too long. Please try again.",
  unsupported: "This browser can't share a location. You can still search for your area by name.",
  insecure: "Location only works on a secure (https) connection.",
};

async function alreadyGranted() {
  try {
    const status = await navigator.permissions?.query({ name: "geolocation" });
    return status?.state === "granted";
  } catch {
    return false;
  }
}

function getPosition() {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy }),
      (err) => {
        const code = err.code === err.PERMISSION_DENIED ? "denied" : err.code === err.TIMEOUT ? "timeout" : "unavailable";
        reject(new LocationError(MESSAGES[code], code));
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  });
}

function showDenied(dialog, message) {
  dialog.querySelector('[data-state="ask"]').hidden = true;
  const denied = dialog.querySelector('[data-state="denied"]');
  denied.hidden = false;
  denied.querySelector('[data-slot="message"]').textContent = message;
  if (!dialog.open) dialog.showModal();
  denied.querySelector("button").focus();
}

/**
 * Ask for the user's location, with an explanation first.
 * @param {string} reason  Why we need it, in plain words.
 * @returns {Promise<{lat:number,lng:number,accuracy:number}>}
 */
export async function requestLocation(reason) {
  const dialog = document.getElementById("location-dialog");
  if (!("geolocation" in navigator)) {
    showDenied(dialog, MESSAGES.unsupported);
    throw new LocationError(MESSAGES.unsupported, "unsupported");
  }
  if (!window.isSecureContext) {
    showDenied(dialog, MESSAGES.insecure);
    throw new LocationError(MESSAGES.insecure, "unsupported");
  }

  if (!(await alreadyGranted())) {
    dialog.querySelector('[data-state="ask"]').hidden = false;
    dialog.querySelector('[data-state="denied"]').hidden = true;
    dialog.querySelector('[data-slot="reason"]').textContent = reason;
    const choice = await new Promise((resolve) => {
      const onClick = (event) => {
        const action = event.target.closest("[data-action]")?.dataset.action;
        if (action) dialog.close(action);
      };
      dialog.addEventListener("click", onClick);
      dialog.addEventListener("close", () => {
        dialog.removeEventListener("click", onClick);
        resolve(dialog.returnValue);
      }, { once: true });
      dialog.returnValue = "cancel";
      dialog.showModal();
    });
    if (choice !== "allow") throw new LocationError("Location not shared.", "cancelled");
  }

  try {
    return await getPosition();
  } catch (error) {
    if (error.code === "denied") {
      const onClick = (event) => {
        if (event.target.closest("[data-action]")) dialog.close();
      };
      dialog.addEventListener("click", onClick);
      dialog.addEventListener("close", () => dialog.removeEventListener("click", onClick), { once: true });
      showDenied(dialog, error.message);
    }
    throw error;
  }
}
