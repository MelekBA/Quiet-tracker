const pushBtn = document.getElementById('enable-push');
const pushStatus = document.getElementById('push-status');

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

console.log("settings.js loaded successfully!");

if (pushBtn) {
    console.log("Push button found in DOM.");

    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.ready.then(reg => {
            reg.pushManager.getSubscription().then(sub => {
                if (sub) {
                    pushStatus.textContent = "✅ Push notifications are active.";
                    pushStatus.style.color = "var(--accent)";
                    pushBtn.textContent = "Update Subscription";
                }
            });
        });
    }

    pushBtn.addEventListener('click', async () => {
        try {
            pushStatus.style.color = "var(--muted)";
            pushStatus.textContent = "Starting...";
            console.log("1. Button clicked");

            if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
                throw new Error("Push notifications are not supported in this browser.");
            }

            pushStatus.textContent = "Requesting permission...";
            console.log("2. Requesting permission...");
            const permission = await Notification.requestPermission();
            console.log("3. Permission result:", permission);
            
            if (permission !== 'granted') {
                throw new Error("Permission denied. Enable notifications in browser settings.");
            }

            pushStatus.textContent = "Fetching public key...";
            console.log("4. Fetching public key...");
            const res = await fetch('/push/public_key');
            if (!res.ok) throw new Error("Failed to fetch public key from server");
            const data = await res.json();
            console.log("5. Got public key:", data.publicKey);

            const convertedKey = urlBase64ToUint8Array(data.publicKey);

            pushStatus.textContent = "Subscribing to push service...";
            console.log("6. Subscribing...");
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: convertedKey
            });
            console.log("7. Subscription successful:", subscription);

            pushStatus.textContent = "Saving to server...";
            console.log("8. Saving subscription to backend...");
            
            const csrfInput = document.querySelector('input[name="csrf_token"]');
            const csrfToken = csrfInput ? csrfInput.value : '';

            const saveRes = await fetch('/push/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(subscription)
            });

            if (!saveRes.ok) throw new Error("Server rejected subscription");

            console.log("9. Done!");
            pushStatus.textContent = "✅ Push notifications enabled successfully!";
            pushStatus.style.color = "var(--accent)";
            pushBtn.textContent = "Update Subscription";
        } catch (err) {
            console.error("PUSH ERROR:", err);
            pushStatus.textContent = "Error: " + err.message;
            pushStatus.style.color = "var(--danger)";
        }
    });
} else {
    console.error("Could not find the push button on the page!");
}