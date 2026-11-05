//! Communication Fabric - Shannon, Nyquist, Convolution
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ChannelMetrics { pub bandwidth_hz: f32, pub snr_linear: f32, pub capacity_bps: f32 }
impl ChannelMetrics {
    pub fn shannon_capacity(bw: f32, snr: f32) -> f32 { bw * (1.0+snr).log2() }
    pub fn nyquist_ok(fs: f32, fmax: f32) -> bool { fs > 2.0*fmax }
    pub fn snr_db(sig: f32, noise: f32) -> f32 { 20.0*(sig/noise.max(1e-9)).log10() }
}
pub fn convolve(x: &[f32], h: &[f32]) -> Vec<f32> { let mut y=vec![0.0; x.len()+h.len()-1]; for i in 0..x.len(){ for j in 0..h.len(){ y[i+j]+=x[i]*h[j]; } } y }
pub fn dft_magnitude(x: &[f32]) -> Vec<f32> { let n=x.len() as f32; (0..x.len()).map(|k|{ let mut re=0.0; let mut im=0.0; for (nn,&xn) in x.iter().enumerate(){ let a=2.0*std::f32::consts::PI*k as f32*nn as f32/n; re+=xn*a.cos(); im-=xn*a.sin(); } (re*re+im*im).sqrt() }).collect() }
#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct CommunicationFabric { pub channels: HashMap<String, ChannelMetrics> }
impl CommunicationFabric { pub fn new()->Self{ Self{ channels: HashMap::new() } } pub fn check_nyquist(&self, fs:f32, fmax:f32)->bool{ ChannelMetrics::nyquist_ok(fs,fmax) } }
