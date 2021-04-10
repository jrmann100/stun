if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/serviceWorker.js');
};

const elements = {
    me: document.querySelector('.me'),
    dial: document.querySelector('section.connect input[type=\'button\']'),
    you: document.querySelector('section.connect input[type=\'text\']'),
    chat: document.querySelector('section.chat'),
    msg: document.querySelector('section.compose input'),

}

const main = async () => {
    const conn = new RTCPeerConnection({
        'iceServers': [{
            'urls': `stun:${location.hostname}:3478`
            // 'urls': 'stun:stun.l.google.com:19302'
        }]
    });

    const server = new WebSocket(`ws://${location.host}/ws`);

    window.server = server; // DEBUG
    window.conn = conn; // DEBUG

    let your_id;

    const send = async (type, body) => server.send(JSON.stringify({ 'type': type, 'body': body }));
    const recv = async (type, timeout = 1000) => {
        return await new Promise((resolve, reject) => {
            function recvHandler(message) {
                const msg = JSON.parse(message.data);
                if (msg['type'] === type) {
                    server.removeEventListener('message', arguments.callee);
                    if (msg['error'])
                        reject(msg['error']);
                    else
                        resolve(msg['body']);
                }
            }
            server.addEventListener('message', recvHandler)
            setTimeout(() => {
                server.removeEventListener('message', recvHandler);
                reject(`recv('${type}') timed out after ${(timeout / 1e3).toPrecision(2)}s`)
            }, timeout)
        })
    }

    const request = async (type, body, timeout = 1000) => { await send(type, body); return await recv(type, timeout); }

    serverOn = (type, callback) => {
        server.addEventListener('message', (message) => {
            const msg = JSON.parse(message.data);
            if (msg['type'] === type) {
                if (msg['error'])
                    throw Error(msg['error']);
                else
                    callback(msg['body']);
            }
        })
    }


    serverOn('candidate_from', async (msg) => await conn.addIceCandidate(msg['candidate']));

    conn.addEventListener('icecandidate', async (ev) => {
        if (ev.candidate) {
            await request('candidate', { 'candidate': ev.candidate, 'id': your_id })
        }
    })

    conn.addEventListener('iceconnectionstatechange', (ev) => console.log('Connection state', conn.iceConnectionState));

    conn.addEventListener('datachannel', (ev) => { chan.set(ev.channel); })

    const chan = {
        _c: undefined,
        create: function () {
            this.set(conn.createDataChannel('data-channel', { ordered: true }));
        },
        get: function () { return this._c; },
        set: function (chan = this._c) {
            this._c = chan;
            this._c.binaryType = "arraybuffer";
            this._c.addEventListener('open', (ev) => new Bubble(`Connected to ${your_id}.`));
            this._c.addEventListener('message', (ev) => new Bubble(ev.data, Bubble.LEFT));
            this._c.addEventListener('close', (ev) => { new Bubble(`Disconnected.`) });
            // todo: shut down everything on dc close. not as easy as callActive; everything needs to be reset,
            // including these callbacks - otherwise you'll get 'connected' 10 times.
            // todo: attempt reconnection?
            // reconnection would probably involve caching messages on reload or downloading history from peer
        }
    }


    const CMyID = class {
        /*static*/ _ta = elements.me;
        /*static*/ _id = '';

        /*static*/ toString() {
            return this._id;
        }

        static get id() {
            return this._id;
        }

        /*static*/ get() {
            return this._id;
        }

        /*static*/ async set(id = this._ta.textContent) {
            if (!(id === '' || id === this._id)) {
                try {
                    this._id = (await request('change_id', { 'id': id }))['id'] === id ? id : _id;
                    localStorage.setItem('id', this._id);
                } catch (e) { console.error(`id ${id} already in use.`); } // todo: need in-UI error-handling.
            }
            this._show();
            return this._id;
        }

        /*static*/ async _show() {
            if (this._ta.textContent !== this._id) this._ta.textContent = this._id;
            if (this._id.length === 0) {
                this._ta.contentEditable = 'false';
            } else {
                this._ta.contentEditable = 'true';
            }
            return this._id;
        }

        /*static*/ async init() {
            this._id = (await request('id'))['id'];
            this._show();
            if (localStorage.getItem('id')) this.set(localStorage.getItem('id'));

            // todo: should reset unsubmitted change on unfocus
            this._ta.addEventListener('keydown', async (e) => {
                if (e.keyCode === 13) {
                    e.preventDefault();
                    await this.set()

                }
            })
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

    MyID = new CMyID(); // Waiting until Safari supports static classes. 
    await MyID.init()

    window.my_id = MyID; // DEBUG

    connectState(true);
    server.addEventListener('close', () => {
        connectState(false);
        MyID.set('');
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

    serverOn('offer_from', async (msg) => {
        if (callActive.get()) return console.warn('Did not ring; another call is active.')
        callActive.set(true);

        // if (!confirm('Incoming call from ID ' + msg['id'] + '\nAccept?')) return;
        // todo: approving calls between clients and monitoring on server-side.
        conn.setRemoteDescription(new RTCSessionDescription(msg['offer']));
        your_id = msg['id'];
        const answer = await conn.createAnswer();
        conn.setLocalDescription(answer);
        await request('answer', { 'answer': answer, 'id': your_id });
    });

    serverOn('error', (msg) => { console.error(msg); });

    elements.you.addEventListener('keydown', async (ev) => {
        if (ev.keyCode === 13) elements.dial.click();
    });

    elements.dial.addEventListener('click', async (ev) => {
        your_id = elements.you.value;
        // todo: cache this?
        if (your_id === MyID.id) {
            throw Error('Please don\'t call yourself.'); // todo: handle all errors in UI.
        } else if (your_id.length === 0) {
            throw Error('Empty target id.');
        }

        if (callActive.get()) return console.warn('Did not dial; another call is active.')
        callActive.set(true);

        chan.create();

        const offer = await conn.createOffer();
        // todo: handshake
        try { await request('offer', { 'offer': offer, 'id': your_id }); } catch (e) {
            if (e.indexOf('no client with ID') !== -1) {
                console.error(e)
                callActive.set(false);
            }
        }
        const answer = await recv('answer_from', 3000);
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