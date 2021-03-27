const elements = {
    me: document.querySelector('.me'),
    dial: document.querySelector('section.connect input[type=\'button\']'),
    you: document.querySelector('section.connect input[type=\'text\']'),
    chat: document.querySelector('section.chat'),
    msg: document.querySelector('section.compose input'),

}

const listenOnce = async (target, event) => new Promise((resolve, reject) => {
    target.addEventListener(event, function (e) {
        target.removeEventListener(event, arguments.callee);
        resolve(e);
    })
})
const main = async () => {
    const conn = new RTCPeerConnection({
        'iceServers': [{
            'urls': 'stun:stun.l.google.com:19302'
        }]
    });

    // is this hostname okay?
    const server = new WebSocket(`ws://${location.hostname}:8765`);

    window.server = server; // DEBUG
    window.conn = conn; // DEBUG

    let my_id, your_id;

    const send = async (type, body) => server.send(JSON.stringify({ 'type': type, 'body': body }));
    const recv = async (type, timeout = 1000) => {
        return await new Promise((resolve, reject) => {
            function recvHandler(message) {
                const msg = JSON.parse(message.data);
                if (msg['type'] === type) {
                    server.removeEventListener('message', arguments.callee);
                    if (msg['body'] && msg['body']['error'])
                        reject(msg['body']);
                    else
                        resolve(msg['body']);
                }
                if (msg['type'] === 'signaling_error') {
                    reject(msg['body'])
                }
            }
            server.addEventListener('message', recvHandler)
            setTimeout(() => {
                server.removeEventListener('message', recvHandler);
                reject(`recv('${type}') timed out after ${(timeout / 1e3).toPrecision(2)}s`)
            }, timeout)
        })
    }

    serverOn = (type, callback) => {
        server.addEventListener('message', (message) => {
            const msg = JSON.parse(message.data);
            if (msg['type'] === type) {
                if (msg['body'] && msg['body']['error'])
                    throw Error(msg['body']);
                else
                    callback(msg['body']);
            }
        })
    }


    serverOn('candidate', async (msg) => await conn.addIceCandidate(msg['candidate']));

    conn.addEventListener('icecandidate', async (ev) => {
        if (ev.candidate) {
            await send('candidate', { 'candidate': ev.candidate, 'id': your_id })
        }
    })

    conn.addEventListener('iceconnectionstatechange', (ev) => console.log('Connection state', conn.iceConnectionState));

    conn.addEventListener('datachannel', (ev) => { chan.set(ev.channel); })

    let chan = {
        _c: undefined,
        create: function () {
            this._c = conn.createDataChannel('data-channel', { ordered: true });
            this._c.binaryType = "arraybuffer";
            this._c.addEventListener('message', (ev) => new Bubble(ev.data, Bubble.LEFT));
            return this._c;
        },
        get: function () { return this._c; },
        set: function (chan) {
            this._c = chan;
            this._c.addEventListener('open', (ev) => console.log(ev));
            this._c.addEventListener('message', (ev) => new Bubble(ev.data, Bubble.LEFT));
            this._c.addEventListener('close', (ev) => console.log(ev));
        }
    }

    window.chan = chan; // DEBUG

    try {
        await new Promise((resolve, reject) => {
            function connectFailedHandler(message) {
                server.removeEventListener('error', arguments.callee);
                reject();
            }
            server.addEventListener('open', () => { server.removeEventListener('error', connectFailedHandler); resolve(); });
            server.addEventListener('error', connectFailedHandler);
        });
    }
    catch (e) {
        elements.me.style.setProperty('--content', '"couldn\'t connect."');
        throw Error('Could not connect to server.');
    }

    const connectState = (state = true) => {
        if (state) {
            elements.dial.removeAttribute('disabled');
            elements.you.removeAttribute('disabled');
        } else {
            elements.you.setAttribute('disabled', '');
            elements.dial.setAttribute('disabled', '');
        }
    }

    connectState(false);

    await send('get_id');

    my_id = await recv('get_id');
    elements.me.textContent = my_id;
    elements.me.setAttribute('contenteditable', '');
    connectState(true);
    server.addEventListener('close', () => {
        connectState(false);
        elements.me.textContent = '';
    })

    let callActive = {
        _value: false,
        get: function () { return this._value; },
        set: function (value) {
            this._value = value;
            if (!this._value) {
                elements.you.addattribute
                elements.dial.removeAttribute('disabled');
            } else {
                elements.dial.setAttribute('disabled', '');
            }
        }
    }

    serverOn('offer', async (msg) => {
        if (callActive.get()) return console.warn('Did not ring; another call is active.')
        callActive.set(true);
        // if (!confirm('Incoming call from ID ' + msg['id'] + '\nAccept?')) return;
        // todo: approving calls between clients and monitoring on server-side.
        conn.setRemoteDescription(new RTCSessionDescription(msg['offer']));
        your_id = msg['id'];
        const answer = await conn.createAnswer();
        conn.setLocalDescription(answer);
        await send('answer', { 'answer': answer, 'id': your_id });
    });

    serverOn('error', (msg) => { throw Error('Server says: ' + msg); });

    elements.dial.addEventListener('click', async (ev) => {
        if (callActive.get()) return console.warn('Did not dial; another call is active.')
        callActive.set(true);

        chan.create();

        const offer = await conn.createOffer();

        your_id = elements.you.value;

        if (your_id === my_id) {
            throw Error('Please don\'t call yourself.'); // todo: handle all errors in UI.
        }

        await send('offer', { 'offer': offer, 'id': your_id });
        const answer = await recv('answer', 3000);
        conn.setLocalDescription(offer);
        conn.setRemoteDescription(new RTCSessionDescription(answer['answer']));
    })


    elements.msg.addEventListener('keydown', async e => {
        if (e.key !== 'Enter' || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey) return;
        e.preventDefault();
        if (e.target.value.trim() !== '') {
            await chan.get().send(e.target.value);
            new Bubble(e.target.value, Bubble.RIGHT);
            e.target.value = '';
        }
    })
}

class Bubble {
    static get CENTER() {
        return 'center';
    }
    static get LEFT() {
        return 'left';
    }
    static get RIGHT() {
        return 'right';
    }

    constructor(text, style = Bubble.CENTER) {
        const b = document.createElement('div');
        const c = elements.chat;
        c.style.setProperty('--timestamp', '\'' + new Date().toLocaleTimeString() + '\'')
        c.style.setProperty('--timestamp-pos', style);
        b.classList.add('bubble');
        b.textContent = text;
        if (style === Bubble.LEFT) {
            b.classList.add('bubble-left')
        } else if (style === Bubble.RIGHT) {
            b.classList.add('bubble-right');
        }
        const jump = c.scrollTopMax === 0 || c.scrollTop / c.scrollTopMax == 1
        c.appendChild(b);
        if (jump) {
            c.scrollTo({
                top: c.scrollHeight
            });
        }
    }
}

main();