
#include <SPI.h>
#include <timer.h>
#include <EEPROMex.h>
#include <Adafruit_SleepyDog.h>
#include <UIPEthernet.h>

boolean dhcp = false; // true или false
Timer<1> timer;
byte __ip[] = {192, 168, 0, 179}; // тут адреса задаются, ip
byte __gateway[] = {192, 168, 0, 200}; // шлюз
EthernetServer server(80);
byte _mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };

byte __butns[] = { 0, 0, 0, 0, 0, 0 };
byte __pins[] = { 4, 5, 6, 7, 8, 9 }; // тут пины на запись, при загрузке ставится HIGH

byte __rpins[] = { A0, A1, A2, A3, A4, A5, A6, A7 }; // тут пины на чтение

void (*SoftReset)(void) = 0;

void setup()
{
    for (byte i = 0; i < 6; i++) {
        pinMode(__pins[i], OUTPUT);
        digitalWrite(__pins[i], HIGH);
    }

    for (byte i = 0; i < 8; i++) {
        pinMode(__rpins[i], INPUT);
    }

    Serial.begin(115200);
    while (!Serial) {;}

    //dhcp = (boolean)EEPROM.readByte(0);
    for (byte i = 0; i < 4; i++) {
      //__ip[i] = EEPROM.readByte(i + 1);
      //__gateway[i] = EEPROM.readByte(i + 5);
    }

    IPAddress my_ip(__ip[0], __ip[1], __ip[2], __ip[3]);
    Serial.print(F("My IP: ")); Serial.println(my_ip);
    IPAddress my_gate(__gateway[0], __gateway[1], __gateway[2], __gateway[3]);
    Serial.print(F("My Gateway: ")); Serial.println(my_gate);
    Serial.print(F("My DHCP: ")); Serial.println(dhcp);

    Watchdog.enable(8000);
    timer.every(200, [](void *) -> bool { Watchdog.reset(); Ethernet.maintain(); return true; });

    if(dhcp) {
        Ethernet.begin(_mac);
    } else {
        Ethernet.begin(_mac, __ip, __gateway, __gateway);
    }

    delay(2000);
    server.begin();
}

void sendStatus(EthernetClient& client)
{
    // send outputs
    for(byte i = 0; i < 6; i++)
    {
        client.print(__butns[i]);
    }

    client.pritn(" ");

    // send inputs
    for (byte i = 0; i < 8; i++)
    {
        client.print(digitalRead(__rpins[i]));
    }

    client.pritnln("+");

    Serial.print("sendStatus DONE!");
}

void applyStatus(String status)
{
    Serial.print("GOT COMMAND: "); Serial.println(resp);

    // if(__butns[bid] != bval)
    // {
    //     __butns[bid] = bval;
    //     digitalWrite(__pins[bid], bval ? LOW : HIGH);
    //     Serial.print(F("BTN: ")); Serial.print(bid); Serial.print(" = "); Serial.println(bval);
    // }
}

void loop()
{
    timer.tick();

    EthernetClient client = server.available();

    if (client)
    {
        sendStatus(client);

        delay(500);
        String resp = "";

        while (client.connected())
        {
            if (client.available())
            {
                 const char c = client.read();
                 resp.concat(c);

                 if (c == '+')
                 {
                     applyStatus(resp);
                     break;
                 }
            }
        }

        delay(500);
        client.stop();
    }
}
