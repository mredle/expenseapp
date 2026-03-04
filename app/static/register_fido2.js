const { startRegistration, startAuthentication } = SimpleWebAuthnBrowser;

// Registration
const statusRegister = document.getElementById("statusRegister");

/**
 * Register Button
 */
document
  .getElementById("btnRegister")
  .addEventListener("click", async () => {
    // Get options
    const resp = await fetch("/auth/generate-registration-options");
    const opts = await resp.json();

    // Start WebAuthn Registration
    let regResp;
    try {
      regResp = await startRegistration(opts);
    } catch (err) {
      if (err.name === 'InvalidStateError' || err.message.toLowerCase().includes('unknown error')) {
          alert("This device is already registered!");
      } else if (err.name === 'NotAllowedError') {
          console.log("User canceled the registration.");
      } else {
          alert("Authenticator error: " + err.message);
      }
      return; // Stop the rest of the function from running
    }

    // Send response to server
    const verificationResp = await fetch(
      "/auth/verify-registration-response",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(regResp),
      }
    );

    // Report validation response
    const verificationRespJSON = await verificationResp.json();
    const { verified, msg } = verificationRespJSON;
    if (verified) {
      window.location.href = "/auth/login";
    } else {
      window.location.reload();
    }
  });
