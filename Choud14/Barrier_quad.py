import numpy as np, matplotlib.pyplot as p, scipy.special
import cosmolopy.perturbation as pb
import cosmolopy.density as cd
from scipy.integrate import quad, tplquad
import itertools
from scipy.interpolate import interp1d
from scipy.interpolate import RectBivariateSpline as RBS
import optparse, sys
from scipy.optimize import brenth, brentq
from sigmas import *
from common import *
from scipy.ndimage.morphology import binary_dilation
from scipy.special import erfc
from joblib import Parallel, delayed
import multiprocessing
num_cores = multiprocessing.cpu_count()

# o = optparse.OptionParser()
# o.add_option('-d','--del0', dest='del0', default=5.)
# o.add_option('-m','--mul', dest='mul', default=1.)
# o.add_option('-z','--red', dest='red', default=12.)
# opts,args = o.parse_args(sys.argv[1:])
# print opts, args



def gam(RL):
	return sig1m(RL)/np.sqrt(sig0(RL)*sigG(RL,2))
def Vstar(RL):
	return (6*np.pi)**1.5*np.sqrt(sigG(RL,1)/sigG(RL,2))**3.
def erf(x):
	return scipy.special.erf(x)
def prob(x,av=0.5,var=0.25):
	return 1/np.sqrt(2*np.pi*var)/x*np.exp(-(np.log(x)-av)**2/2/var)
def F(x):
	return (x**3-3*x)/2*(erf(x*np.sqrt(5./2))+erf(x*np.sqrt(5./8)))+np.sqrt(2./5/np.pi)*((31.*x**2/4+8./5)*np.exp(-5.*x**2/8)+(x**2/2-8./5)*np.exp(-5.*x**2/2))
                                                 #?????
def pG(y,av,var):
	return 1/np.sqrt(2*np.pi*var)*np.exp(-(y-av)**2/2/var)
def B(z,beta,s):
	#return Deltac(z)+beta*np.sqrt(s)
	return Deltac(z)+beta*np.sqrt(s)
def Q(m,M0, eps=1.e-4):
	#return 1.
	r,R0 = m2R(m), m2R(M0)
	s,s0 = sig0(r), sig0(R0)
	sx = SX(r,R0)
	Q = 1-sx**2/s/s0
	if Q <= eps:
		print 'Q {}<eps={}, recompute with quad'.format(Q, eps)
		print 'm, M0, r, R0', m, M0, r, R0
		s,s0 = sig0(r, method='quad'), sig0(R0, method='quad')
		sx = SX(r,R0, method='quad')
		Q = 1-sx**2/s/s0 + 1.e-12
		print 'quad Q=', Q
		if Q <= 0: raise(Exception)
	#print m, M0, Q
	return Q


def oepX(m, M0):
	r,R0 = m2R(m), m2R(M0)
	s,s0 = sig0(r), sig0(R0)
	sx = SX(r,R0)
	dsx = SX(1.0005*r, R0)-SX(0.9995*r, R0)
	ds = sig0(1.0005*r) - sig0(0.9995*r)
	return 2*s/sx*dsx/ds
def epX(m,M0):
	#return oepX(m, M0)
	r,R0 = m2R(m), m2R(M0)
	s,s0 = sig0(r), sig0(R0)
	sx = SX(r,R0)
	sg1m = sig1m(r)
	sg1mX = sig1mX(r,R0)
	return (s*sg1mX/sx/sg1m)


def get_varx(gamm, epx, q):
	res = 1-gamm**2-gamm**2*(1-epx)**2*(1-q)/q 
	if res <= 0. or q< 1.e-9:
		print 'VARX: Small q, asymptoting second term', gamm**2*(1-epx)**2, q 
		return 1-gamm**2 * (1 + 0.)
	else:
		return res
#def trapz(x,y):
#	return (x[-1]*y[-1]-x[0]*y[0]+np.sum(x[1:]*y[:-1]-y[1:]*x[:-1]))/2
def trapz(x,y):
	return np.trapz(y,x=x)

# def subgrand_trapz_log(b,del0,s,s0,sx,epx,q,meanmu,varmu,varx,gamm,R0,V,z,err=False):
# 	# EqA8, log intervaled integration axis
# 	Bb = B(z,b,s)
# 	#print 'gamm,epx,q =',gamm,epx,q 
# 	meanx = gamm*((Bb-del0*sx/s0)*(1-epx)/q/np.sqrt(s)+Bb*epx/np.sqrt(s))
# 	fact = V/Vstar(R0)*pG(Bb/np.sqrt(s),meanmu, varmu)
# 	#print b, Bb/np.sqrt(s),meanmu,varmu,pG(Bb/np.sqrt(s),meanmu, varmu)
# 	#print b
# 	lxmin,lxmax = np.log(b*gamm), np.log(100.)
# 	lx = np.linspace(lxmin,lxmax,100)
# 	x = np.exp(lx)
# 	y = (x/gamm-b)*F(x)*pG(x,meanx,varx)*x
# 	factint = trapz(x,y)
# 	#print y
# 	#print factint
# 	#factint = quad(lambda x: (x/gamm-b)*F(x)*pG(x,meanx,varx),b*gamm,100)[0]
# 	#print fact, factint
# 	return fact*factint

def subgrand_trapz(b,del0,s,s0,sx,epx,q,meanmu,varmu,varx,gamm,r,V,z,err=False):
	# EqA8, non-log intervaled integration axis
	Bb = B(z,b,s)
	#print 'gamm,epx,q =',gamm,epx,q 
	meanx = gamm*((Bb-del0*sx/s0)*(1-epx)/q/np.sqrt(s)+Bb*epx/np.sqrt(s))
	fact = V/Vstar(r)*pG(Bb/np.sqrt(s),meanmu, varmu)   #!!!!
	#print b, Bb/np.sqrt(s),meanmu,varmu,pG(Bb/np.sqrt(s),meanmu, varmu)
	#print b
	#x = np.linspace(b*gamm,100.,200)   
	                       #TUNE
	x = np.logspace(np.log10(b*gamm),5,200)
	y = (x/gamm-b)*F(x)*pG(x,meanx,varx)
	factint = np.trapz(y,x)
	#print np.log10(b*gamm), fact, factint
	return fact*factint
def _blims(b, y, factor=1.e-6):
	"""Integration limits used internally by the sigma_r functionp."""
	maxintegrand = np.max(np.abs(y))
	highmask = np.abs(y) > maxintegrand * factor
	highmask = binary_dilation(highmask)
	minb = np.min(b[highmask])
	maxb = np.max(b[highmask])
	return minb, maxb

def _integrand_trapz_y(b,del0,s,s0,sx,epx,q,meanmu,varmu,varx,gamm,r,V,z):
	y = []
	for bx in b:
		newy = prob(bx)*subgrand_trapz(bx,del0,s,s0,sx,epx,q,meanmu,varmu,varx,gamm,r,V,z)/2/s
		if np.isnan(newy): 
			print 'NAN detected, breaking at: '
			print bx,prob(bx),del0,s,s0,sx,epx,q,meanmu,varmu,varx,gamm,r,V
			break
		else:
			y.append(newy)
	return np.asarray(y)

def integrand_trapz(del0,m,M0,R0,z):  #2s*f_ESP
	# of A7, divided by 2s; this IS f_ESP
	s = sig0(m2R(m))
	V,r,dmdr = pb.volume_radius_dmdr(m,**cosmo)
	#V *= RcovEul(del0, z)**3 #convert to eulerian volume
	s,s0,sx = sig0(r), sig0(R0),SX(r,R0)
	gamm = gam(r)
	epx,q = epX(m,M0), Q(m,M0)
	meanmu = del0/np.sqrt(s)*sx/s0
	varmu = q
	varx = get_varx(gamm, epx, q)
	#print varmu, varx

	#b = np.arange(0.00001,30.,0.03)                      #TUNE
	b = np.logspace(-6,3,100)
	y = _integrand_trapz_y(b,del0,s,s0,sx,epx,q,meanmu,varmu,varx,gamm,r,V,z)
	if (y==0.).all(): return 0.
	blims = _blims(b, y)
	while blims[0] == blims[1]:
		b = np.logspace(np.log10(blims[0]*0.99),np.log10(blims[1]*1.01),100)
		y = _integrand_trapz_y(b,del0,s,s0,sx,epx,q,meanmu,varmu,varx,gamm,r,V,z)
		blims = _blims(b, y)
	b = np.logspace(np.log10(blims[0]),np.log10(blims[1]),200)
	y = _integrand_trapz_y(b,del0,s,s0,sx,epx,q,meanmu,varmu,varx,gamm,r,V,z)
	if y[-1]/np.max(y)>1.E-3: 
		print "Warning: choice of bmax too small"
		print y
		print blims
		import IPython; IPython.embed()
		raise(Exception)
	if y[0]/np.max(y)>1.E-3: 
		print "Warning: choice of bmin too big"
	return np.trapz(y,b)
	#return quad(lambda b: prob(b)*subgrand_trapz(b,del0,m,M0,z),0,4.)[0]/2/s
def dsdm(m):
	return np.abs(sig0(m2R(m+1))-sig0(m2R(m-1)))/2
# def fcoll(del0,M0,z):
# 	mm = mmin(z)
# 	R0 = m2R(M0)
# 	return quad(lambda m: integrand_trapz(del0,m,M0,R0,z)*dsdm(m),mm,M0)
# def fcoll_trapz(del0,M0,z):
# 	mm = mmin(z)
# 	R0 = m2R(M0)
# 	mx = np.arange(mm,M0,mm)
# 	y = []
# 	for m in mx:
# 		y.append(integrand_trapz(del0,m,M0,R0,z)*dsdm(m))
# 		print m, y[-1]
# 	return np.trapz(y,mx,dx=mm)
# 	#eturn trapz(mx,y)
# def fcoll_trapz_log(del0,M0,z,debug=False):
# 	# Eq. (6)
# 	print del0
# 	mm = mmin(z)
# 	R0 = m2R(M0)
# 	lmx = np.linspace(np.log(mm),np.log(M0),200)

# 	y = []
# 	for lm in lmx:
# 		m = np.exp(lm)
# 		y.append(integrand_trapz(del0,m,M0,R0,z)*dsdm(m)*m) #dsdm*m=ds/dln(m)
# 	if debug: 
# 		return trapz(lmx,y),np.exp(lmx),y
# 	else:
# 		return trapz(lmx,y)

def fcoll_trapz_log(del0,M0,z,debug=False):
	# Eq. (6)
	print del0
	mm = mmin(z)
	R0 = m2R(M0)
	mx = np.logspace(np.log10(mm),np.log10(M0),200)
	ls = sig0(m2R(mx))
	y = []
	for m in mx:
		y.append(integrand_trapz(del0,m,M0,R0,z))
	if debug: 
		return trapz(lmx,y),np.exp(lmx),y
	else:
		#print ls[::-1],y[::-1]
		return trapz(ls[::-1],y[::-1])


	

#
def resinterp(x1,x2,y1,y2):
	if y1*y2>0: raise ValueError('resinterp: root not in range')
	else:
		return (y2*x1-y1*x2)/(y2-y1)

if __name__ == "__main__":
	

	zeta = 40.

	# Z = float(opts.red)
	# M0 = zeta*mmin(Z)*float(opts.mul)
	# del0 = float(opts.del0)
	Z = 12.
	#M0 = zeta*mmin(Z)
	#Mlist = np.exp(np.linspace(np.log(M0),np.log(1000*M0),10))
	#Slist = np.arange(5.,6.,1.)
	Slist = np.logspace(-1, np.log10(15.), 6)
	Mlist = S2M(Slist)
	
	#dlist = np.linspace(8,10,16)
	# for del0 in dlist:
	# 	res = fcoll_trapz_log(del0,M0,Z)
	# 	print m2S(M0), res[0]
	#Bracks = (())
	# def parafunc(S0,Z):
	# 	M0 = S2M(S0)
	# 	def newfunc(del0):
	# 		return fcoll_trapz_log(del0,M0,Z)*40-1
	# 	return brentq(newfunc,11,14.5,xtol=1.E-3,maxiter=100)
	if False:
		reslist = Parallel(n_jobs=num_cores)(delayed(parafunc)(S0,Z) for S0 in Slist)
		print reslist
		p.figure()
		p.plot(Slist,reslist)
		p.show()
	elif True:
		try:
			rootlist = []
			for xind, M0 in enumerate(Mlist):
				def newfunc(del0):
					res = fcoll_trapz_log(del0,M0,Z)*zeta-1
					#res = fcoll_FZH(del0,M0,Z)*40-1
					return res
				Dlist = np.linspace(3.,15.,4)
				NJOBS = min(Dlist.size, num_cores)
				reslist = Parallel(n_jobs=NJOBS)(delayed(newfunc)(d0) for d0 in Dlist)
				print reslist

				if reslist[0]*reslist[-1]>0: 
					print "root not in range"
					break
				else:
					for ite in xrange(1):
						i = 0
						while reslist[i]*reslist[-1]<0: i+=1
						Dlist2 = np.linspace(Dlist[i-1],Dlist[i],4)
						reslist = Parallel(n_jobs=NJOBS)(delayed(newfunc)(d0) for d0 in Dlist2)
						print reslist
					i = 0
					while reslist[i]*reslist[-1]<0: i+=1
					resroot = resinterp(Dlist2[i-1],Dlist2[i],reslist[i-1],reslist[i])
					print 'Barrier height at {}: {}'.format(Slist[xind], resroot)
					rootlist.append(resroot)
			print rootlist

			p.figure()
			p.plot(Slist,rootlist, label='z={}'.format(Z))
			p.xlabel('S0')
			p.ylabel('B')
			p.legend()
			p.savefig('barrier_z{}.png'.format(Z))
		except:
			e = sys.exc_info()
			print e, '\n'
		finally:
			memory.clear()

		
	else:
		print 'doing nothing'
		#tplquad(All,mmin,M0,lambda x: 0, lambda x: 5., lambda x,y: gam(m2R(x))*y,lambda x,y: 10.,args=(del0,M0,z))

