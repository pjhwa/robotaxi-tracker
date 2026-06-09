import { useState, useEffect } from "react";
import styles from "./Header.module.css";
import { fetchVapidPublicKey, subscribePush, unsubscribePush } from "../api";

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = atob(base64);
    return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
}

export default function Header({ lastUpdated }) {
    const ago = lastUpdated
        ? Math.round((Date.now() - new Date(lastUpdated).getTime()) / 60000)
        : null;

    const pushSupported = typeof window !== 'undefined'
        && 'serviceWorker' in navigator
        && 'PushManager' in window;

    const [subscribed, setSubscribed] = useState(false);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!pushSupported) return;
        navigator.serviceWorker.ready.then(reg =>
            reg.pushManager.getSubscription()
        ).then(sub => setSubscribed(!!sub)).catch(() => {});
    }, [pushSupported]);

    async function handleSubscribe() {
        setLoading(true);
        try {
            const reg = await navigator.serviceWorker.ready;
            const { publicKey } = await fetchVapidPublicKey();
            const sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey),
            });
            await subscribePush(sub.toJSON());
            setSubscribed(true);
        } catch (e) {
            console.error("Subscribe failed:", e);
        } finally {
            setLoading(false);
        }
    }

    async function handleUnsubscribe() {
        setLoading(true);
        try {
            const reg = await navigator.serviceWorker.ready;
            const sub = await reg.pushManager.getSubscription();
            if (sub) {
                await sub.unsubscribe();
                await unsubscribePush(sub.toJSON().endpoint);
            }
            setSubscribed(false);
        } catch (e) {
            console.error("Unsubscribe failed:", e);
        } finally {
            setLoading(false);
        }
    }

    return (
        <header className={styles.header}>
            <div className={styles.brand}>
                <span className={styles.title}>Texas Robotaxi Tracker</span>
                <span className={styles.subtitle}>Powered by TxMCCS</span>
            </div>
            <div className={styles.right}>
                {pushSupported && (
                    <button
                        className={subscribed ? styles.notifyOff : styles.notifyOn}
                        onClick={subscribed ? handleUnsubscribe : handleSubscribe}
                        disabled={loading}
                    >
                        {loading ? "..." : subscribed ? "알림 끄기" : "알림 받기"}
                    </button>
                )}
                <div className={styles.status}>
                    <span className={styles.liveDot} />
                    <span className={styles.liveLabel}>Live</span>
                    <span className={styles.updatedAt}>
                        {ago !== null ? `Updated ${ago}m ago` : "No data"}
                    </span>
                </div>
            </div>
        </header>
    );
}
