import url from "url";
import crypto from "crypto";

const parsed = url.parse("https://example.com");
const cipher = crypto.createCipher("aes-256-cbc", "key");
