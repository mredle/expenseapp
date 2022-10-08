const { startRegistration, startAuthentication } = SimpleWebAuthnBrowser;

// Authentication
const statusAuthenticate = document.getElementById("statusAuthenticate");
const dbgAuthenticate = document.getElementById("dbgAuthenticate");

/**
 * Authenticate Button
 */
document
  .getElementById("btnAuthenticate")
  .addEventListener("click", async () => {
    // Get options
    const resp = await fetch("/auth/generate-authentication-options");
    const opts = await resp.json();

    // Start WebAuthn Authentication
    let authResp;
    try {
      authResp = await startAuthentication(opts);
    } catch (err) {
      throw new Error(err);
    }

    // Send response to server
    const verificationResp = await fetch(
      "/auth/verify-authentication-response",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(authResp),
      }
    );

    // Report validation response
    const verificationRespJSON = await verificationResp.json();
    const { verified, msg } = verificationRespJSON;
    if (verified) {
      window.location.href = "/auth/authenticate_fido2_success";
    } else {
      window.location.href = "/auth/authenticate_fido2_error";
    }
  });
