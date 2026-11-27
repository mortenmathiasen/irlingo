# An ESP32 in another place

An ESP32 with an IR LED can sit on another network than Home Assistant's, e.g.
in a summer house, and still be controlled from Home Assistant at home. Only
the ESP32 is needed there: it connects home through a
[WireGuard](https://www.wireguard.com/) tunnel, and Home Assistant reaches it
through that tunnel. This works the same for the
[ESPHome component](esphome.md) and for an emitter used by the
[Home Assistant integration](home-assistant.md).

Tested with Home Assistant 2026.11 on Home Assistant OS, the community
WireGuard app 0.14 and ESPHome 2026.11.

- [How it works](#how-it-works)
- [At home: the WireGuard app](#at-home-the-wireguard-app)
- [On the ESP32](#on-the-esp32)
- [In Home Assistant](#in-home-assistant)
- [Moving the ESP32](#moving-the-esp32)
- [Troubleshooting](#troubleshooting)

## How it works

```
summer house                         home
ESP32 ── Wi-Fi ── router ── internet ── router (UDP 51820) ── Home Assistant
172.27.66.2  ═════════ WireGuard tunnel ═════════  WireGuard app 172.27.66.1
```

- The ESP32 opens the tunnel and keeps it open, so nothing needs to be set up
  on the summer house's router.
- At home, the router forwards UDP port 51820 to Home Assistant, and a
  dynamic DNS name, e.g. from [DuckDNS](https://www.duckdns.org/), finds the
  home's public address.
- The WireGuard app runs in its own container, not on Home Assistant's
  network, so Home Assistant cannot reach the tunnel's addresses directly.
  The app therefore forwards the ESPHome ports, 6053 (API) and 3232 (firmware
  updates), from its own address to the ESP32. Home Assistant connects to the
  app's host name, `a0d7b954-wireguard`, and ends up on the ESP32.

Pick tunnel addresses outside every network involved; `172.27.66.0/24` is an
example. If the home network is e.g. `10.0.0.0/8`, a tunnel in `10.x` would
clash with it.

If Tailscale is installed too, the two do not conflict: they use different
interfaces and addresses.

## At home: the WireGuard app

1. Forward UDP port 51820 on the home router to Home Assistant's address.
2. Install the *WireGuard* app from the community app repository (Settings →
   Apps), and configure it, with your own host name:

   ```yaml
   server:
     host: myhome.duckdns.org
     addresses:
       - 172.27.66.1
     dns: []
     post_up: >-
       iptables -A FORWARD -i %i -j ACCEPT;
       iptables -A FORWARD -o %i -j ACCEPT;
       iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE;
       iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 6053 -j DNAT --to-destination 172.27.66.2;
       iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 3232 -j DNAT --to-destination 172.27.66.2;
       iptables -t nat -A POSTROUTING -o %i -j MASQUERADE
     post_down: >-
       iptables -D FORWARD -i %i -j ACCEPT;
       iptables -D FORWARD -o %i -j ACCEPT;
       iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE;
       iptables -t nat -D PREROUTING -i eth0 -p tcp --dport 6053 -j DNAT --to-destination 172.27.66.2;
       iptables -t nat -D PREROUTING -i eth0 -p tcp --dport 3232 -j DNAT --to-destination 172.27.66.2;
       iptables -t nat -D POSTROUTING -o %i -j MASQUERADE
   peers:
     - name: ir-summerhouse
       addresses:
         - 172.27.66.2
       allowed_ips: []
       client_allowed_ips:
         - 172.27.66.0/24
   ```

   Peer names may hold letters, digits and `-`, not `_`.
3. Start the app. It writes the peer's configuration to
   `/ssl/wireguard/ir-summerhouse/client.conf`, e.g. readable with the File
   editor app. Its `PrivateKey` is the ESP32's private key; the `PublicKey`
   under `[Peer]` is the server's public key.

One forwarded port pair serves one ESP32. For a second one, forward other
ports to it and set its API port (`api: port:`) and OTA port to match.

## On the ESP32

Add the summer house's Wi-Fi, the tunnel and a clock (WireGuard needs the
time), and tell ESPHome Builder to reach the device through the app:

```yaml
wifi:
  networks:
    - ssid: !secret wifi_ssid
      password: !secret wifi_password
    - ssid: "Summer house"
      password: !secret summerhouse_wifi_password
  use_address: a0d7b954-wireguard

time:
  - platform: sntp

wireguard:
  address: 172.27.66.2
  private_key: !secret wg_private_key
  peer_endpoint: myhome.duckdns.org
  peer_port: 51820
  peer_public_key: !secret wg_server_public_key
  peer_allowed_ips:
    - 172.27.66.0/24
  peer_persistent_keepalive: 25s
```

Put the keys from `client.conf` and the Wi-Fi password in ESPHome Builder's
secrets. With both networks listed, the ESP32 joins whichever is in range, so
it can be tested at home first: the tunnel comes up from the home network too.

The ESP32 must find a 2.4 GHz network; most ESP32 chips cannot use 5 GHz.

## In Home Assistant

Point the ESPHome integration at the app: Settings → Devices & services →
ESPHome → the device → ⋮ → *Reconfigure*, host `a0d7b954-wireguard`, port
6053. Home Assistant then connects through the tunnel; the WireGuard app's log
shows the ESP32's latest handshake and its public address.

While the ESP32 is on the home network, Home Assistant discovers it by mDNS
and may set the host back to its address on the home network. To stop that,
turn mDNS off on the ESP32; it is not needed once the host is set by hand:

```yaml
mdns:
  disabled: true
```

ESPHome Builder may then show the device as offline although it works.

## Moving the ESP32

1. Unplug it at home, soon after setting the host, so mDNS has no time to
   change it back.
2. Plug it in at the new place, and wait a minute or two for Wi-Fi, the clock
   and the tunnel.
3. Check the host in the integration (see above) and correct it if it holds a
   home network address.
4. Send something, e.g. from a dashboard card.

## Troubleshooting

- **The entities stay unavailable:** check the integration's host, then the
  WireGuard app's log for a recent handshake from the ESP32.
- **No handshake:** the ESP32 has no Wi-Fi or no clock yet, the home router
  does not forward UDP 51820, or the dynamic DNS name points to an old address.
  If the ESP32 cannot join a network, it opens its fallback hotspot (`ap:`) after
  a minute; check the network name, the password and that it is 2.4 GHz.
- **Firmware updates fail with "No route to host" to a home network address:**
  ESPHome Builder remembers the address it last discovered. Restart the
  *ESPHome Device Builder* app; it then uses `use_address`.
- **A firmware update over the tunnel fails:** check that port 3232 is
  forwarded in `post_up`; the first install can always be done over USB.
