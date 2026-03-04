const { startAuthentication } = SimpleWebAuthnBrowser;

// Run automatically when the page loads
document.addEventListener("DOMContentLoaded", async () => {
  try {
    // 1. Get options from the server
    const resp = await fetch("/auth/generate-authentication-options");
    const opts = await resp.json();

    // 2. Start WebAuthn Authentication automatically
    let authResp;
    try {
      authResp = await startAuthentication(opts);
    } catch (err) {
      // If the user cancels, ignores the prompt, or no key is found on the device
      console.warn("FIDO2 auth canceled or failed:", err);
      window.location.href = "/auth/authenticate_password";
      return; // Stop execution
    }

    // 3. Send response to server
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

    // 4. Report validation response
    const verificationRespJSON = await verificationResp.json();
    const { verified, msg } = verificationRespJSON;
    
    if (verified) {
      window.location.href = "/auth/authenticate_fido2_success";
    } else {
      alert("Login failed: " + (msg || "Unknown error"));
      window.location.href = "/auth/authenticate_fido2_error";
    }
    
  } catch (err) {
    // Catch any other unexpected network errors and fallback to password
    console.error("Critical error during authentication:", err);
    window.location.href = "/auth/authenticate_password";
  }
});