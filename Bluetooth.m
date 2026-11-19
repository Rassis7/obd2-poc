#import <Foundation/Foundation.h>
#import <CoreBluetooth/CoreBluetooth.h>
#import <IOBluetooth/IOBluetooth.h>
#import <AppKit/AppKit.h>
#import <unistd.h>

static void fail(NSString *message) {
    fprintf(stderr, "%s\n", message.UTF8String);
    exit(1);
}
static void emit(NSString *key, NSString *name, NSString *transport) {
    if (!key) return;
    NSData *json = [NSJSONSerialization dataWithJSONObject:@{@"id":key, @"name":name ?: @"Sem nome", @"transport":transport} options:0 error:nil];
    fwrite(json.bytes, 1, json.length, stdout); puts(""); fflush(stdout);
}
@interface Radio : NSObject<CBCentralManagerDelegate, IOBluetoothDeviceInquiryDelegate, IOBluetoothRFCOMMChannelDelegate, IOBluetoothDevicePairDelegate>
@property CBCentralManager *central;
@property IOBluetoothDeviceInquiry *inquiry;
@property IOBluetoothRFCOMMChannel *channel;
@property IOBluetoothDevicePair *pair;
@property IOBluetoothDevice *device;
@end
@implementation Radio
- (void)centralManagerDidUpdateState:(CBCentralManager *)manager {
    if (manager.state == CBManagerStatePoweredOn)
        [manager scanForPeripheralsWithServices:nil options:nil];
    if (manager.state == CBManagerStateUnauthorized) fail(@"Acesso Bluetooth negado no macOS.");
    if (manager.state == CBManagerStatePoweredOff) fail(@"Bluetooth desligado.");
}
- (void)centralManager:(CBCentralManager *)manager didDiscoverPeripheral:(CBPeripheral *)p advertisementData:(NSDictionary *)data RSSI:(NSNumber *)rssi {
    emit(p.identifier.UUIDString, p.name ?: data[CBAdvertisementDataLocalNameKey], @"ble");
}
- (void)deviceInquiryDeviceFound:(IOBluetoothDeviceInquiry *)sender device:(IOBluetoothDevice *)d {
    emit(d.addressString, d.name, @"classic");
}
- (void)deviceInquiryComplete:(IOBluetoothDeviceInquiry *)sender error:(IOReturn)error aborted:(BOOL)aborted {
    if (error) fail(@"Falha na busca Bluetooth clássico.");
}
- (void)rfcommChannelData:(IOBluetoothRFCOMMChannel *)c data:(void *)data length:(size_t)n {
    fwrite(data, 1, n, stdout); fflush(stdout);
}
- (void)rfcommChannelClosed:(IOBluetoothRFCOMMChannel *)c { fail(@"Adaptador desconectado."); }
- (void)openSerial {
    IOBluetoothSDPServiceRecord *cached = [self.device getServiceRecordForUUID:[IOBluetoothSDPUUID uuid16:0x1101]];
    if (cached && [self openRecord:cached]) return;
    if ([self.device performSDPQuery:self] != kIOReturnSuccess) fail(@"Falha na consulta de serviços.");
}
- (void)sdpQueryComplete:(IOBluetoothDevice *)device status:(IOReturn)status {
    IOBluetoothSDPServiceRecord *record = [device getServiceRecordForUUID:[IOBluetoothSDPUUID uuid16:0x1101]];
    if (status || !record) fail(@"Serviço serial SPP indisponível.");
    if (![self openRecord:record]) fail(@"Falha ao abrir o canal serial Bluetooth.");
}
- (BOOL)openRecord:(IOBluetoothSDPServiceRecord *)record {
    BluetoothRFCOMMChannelID cid;
    if ([record getRFCOMMChannelID:&cid]) return NO;
    IOBluetoothRFCOMMChannel *channel = nil;
    if ([self.device openRFCOMMChannelSync:&channel withChannelID:cid delegate:self]) return NO;
    self.channel = channel;
    puts("READY"); fflush(stdout);
    [NSFileHandle fileHandleWithStandardInput].readabilityHandler = ^(NSFileHandle *handle) {
        NSData *data = handle.availableData;
        if (!data.length) exit(0);
        dispatch_async(dispatch_get_main_queue(), ^{
            if (data.length > UINT16_MAX || [channel writeSync:(void *)data.bytes length:(UInt16)data.length]) fail(@"Falha ao enviar consulta.");
        });
    };
    return YES;
}
- (NSAlert *)pairingAlert:(NSString *)message {
    [NSApplication sharedApplication];
    [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];
    [NSApp activateIgnoringOtherApps:YES];
    NSAlert *alert = [NSAlert new];
    alert.messageText = self.device.name ?: self.device.addressString;
    alert.informativeText = message;
    [alert addButtonWithTitle:@"Confirmar"];
    [alert addButtonWithTitle:@"Cancelar"];
    return alert;
}
- (void)devicePairingPINCodeRequest:(IOBluetoothDevicePair *)sender {
    NSAlert *alert = [self pairingAlert:@"Digite o PIN Bluetooth do adaptador."];
    NSSecureTextField *field = [[NSSecureTextField alloc] initWithFrame:NSMakeRect(0,0,200,24)];
    alert.accessoryView = field;
    [alert.window setInitialFirstResponder:field];
    if ([alert runModal] != NSAlertFirstButtonReturn) fail(@"Pareamento cancelado.");
    NSData *data = [field.stringValue dataUsingEncoding:NSASCIIStringEncoding];
    BluetoothPINCode pin = {0};
    if (!data.length || data.length > sizeof(pin)) fail(@"PIN inválido.");
    [data getBytes:&pin length:data.length];
    [sender replyPINCode:(ByteCount)data.length PINCode:&pin];
}
- (void)devicePairingUserConfirmationRequest:(IOBluetoothDevicePair *)sender numericValue:(BluetoothNumericValue)value {
    NSAlert *alert = [self pairingAlert:[NSString stringWithFormat:@"Confirme o código Bluetooth %06u.", (unsigned)value]];
    [sender replyUserConfirmation:[alert runModal] == NSAlertFirstButtonReturn];
}
- (void)devicePairingFinished:(id)sender error:(IOReturn)err {
    if (err) fail(@"Pareamento recusado. Pareie o adaptador nos Ajustes do Sistema e tente novamente.");
    [self openSerial];
}
@end
int main(int argc, const char **argv) { @autoreleasepool {
    Radio *radio = [Radio new];
    if (argc == 1) {
        radio.central = [[CBCentralManager alloc] initWithDelegate:radio queue:nil];
        for (IOBluetoothDevice *d in IOBluetoothDevice.pairedDevices) emit(d.addressString, d.name, @"classic");
        radio.inquiry = [IOBluetoothDeviceInquiry inquiryWithDelegate:radio];
        radio.inquiry.inquiryLength = 5;
        radio.inquiry.updateNewDeviceNames = NO;
        if ([radio.inquiry start]) fail(@"Busca indisponível. Confira o Bluetooth e as permissões.");
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:8]];
    } else {
        radio.device = [IOBluetoothDevice deviceWithAddressString:@(argv[1])];
        if (!radio.device) fail(@"Endereço inválido.");
        if (radio.device.isPaired) [radio openSerial];
        else {
            radio.pair = [IOBluetoothDevicePair pairWithDevice:radio.device];
            radio.pair.delegate = radio;
            if ([radio.pair start]) fail(@"Não foi possível iniciar o pareamento.");
        }
        [[NSRunLoop currentRunLoop] run];
    }
    (void)radio.central;
} return 0; }
