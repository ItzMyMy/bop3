"""Read and write Minecraft's servers.dat (the multiplayer server list): uncompressed NBT, a root
compound holding a "servers" list of compounds with "name" and "ip" (plus optional "icon" etc.).

Only the NBT tag types a server list uses are supported; other tags are kept as raw bytes when read.

  python servers_dat.py <servers.dat>                     list the servers
  python servers_dat.py <servers.dat> add <name> <ip>     add a server (or rename the one with that ip)
"""
import struct, sys

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY = range(13)
FIXED = {BYTE: ">b", SHORT: ">h", INT: ">i", LONG: ">q", FLOAT: ">f", DOUBLE: ">d"}


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, n):
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self):
        return self.take(self.unpack(">H")).decode("utf-8")

    def payload(self, tag):
        if tag in FIXED:
            return self.unpack(FIXED[tag])
        if tag == STRING:
            return self.string()
        if tag == BYTE_ARRAY:
            return self.take(self.unpack(">i"))
        if tag in (INT_ARRAY, LONG_ARRAY):
            n = self.unpack(">i")
            return [self.unpack(">i" if tag == INT_ARRAY else ">q") for _ in range(n)]
        if tag == LIST:
            item, n = self.unpack(">b"), self.unpack(">i")
            return (item, [self.payload(item) for _ in range(n)])
        if tag == COMPOUND:
            out = {}
            while (t := self.unpack(">b")) != END:
                name = self.string()
                out[name] = (t, self.payload(t))
            return out
        raise ValueError(f"unsupported NBT tag {tag}")


def write_payload(tag, value):
    if tag in FIXED:
        return struct.pack(FIXED[tag], value)
    if tag == STRING:
        b = value.encode("utf-8")
        return struct.pack(">H", len(b)) + b
    if tag == BYTE_ARRAY:
        return struct.pack(">i", len(value)) + value
    if tag in (INT_ARRAY, LONG_ARRAY):
        return struct.pack(">i", len(value)) + b"".join(struct.pack(">i" if tag == INT_ARRAY else ">q", v) for v in value)
    if tag == LIST:
        item, items = value
        return struct.pack(">bi", item, len(items)) + b"".join(write_payload(item, v) for v in items)
    if tag == COMPOUND:
        out = b""
        for name, (t, v) in value.items():
            out += struct.pack(">b", t) + write_payload(STRING, name) + write_payload(t, v)
        return out + struct.pack(">b", END)
    raise ValueError(f"unsupported NBT tag {tag}")


def load(path):
    """The list of server compounds ({key: (tag, value)}) in a servers.dat."""
    r = Reader(open(path, "rb").read())
    if r.unpack(">b") != COMPOUND:
        raise ValueError(f"{path}: not an NBT compound")
    r.string()
    root = r.payload(COMPOUND)
    return root.get("servers", (LIST, (COMPOUND, [])))[1][1]


def save(path, servers):
    root = {"servers": (LIST, (COMPOUND, servers))}
    open(path, "wb").write(struct.pack(">b", COMPOUND) + write_payload(STRING, "") + write_payload(COMPOUND, root))


def server(name, ip):
    return {"name": (STRING, name), "ip": (STRING, ip)}


def add(servers, name, ip):
    """Add name/ip, or rename the existing entry with that ip. Returns True if anything changed."""
    for s in servers:
        if s.get("ip", (STRING, ""))[1].lower() == ip.lower():
            if s.get("name", (STRING, ""))[1] == name:
                return False
            s["name"] = (STRING, name)
            return True
    servers.append(server(name, ip))
    return True


if __name__ == "__main__":
    path = sys.argv[1]
    servers = load(path)
    if len(sys.argv) > 2 and sys.argv[2] == "add":
        changed = add(servers, sys.argv[3], sys.argv[4])
        if changed:
            save(path, servers)
        print("added/renamed" if changed else "already there")
    for s in load(path):
        print(f"  {s.get('name', (0, '?'))[1]}  ->  {s.get('ip', (0, '?'))[1]}")
